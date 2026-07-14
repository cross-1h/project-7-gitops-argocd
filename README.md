# Project 7: GitOps Delivery with ArgoCD

In every project so far, your pipeline deployed by pushing into the cluster. In this one, it stops. You will move to **GitOps**: git becomes the single source of truth for what should be running, and ArgoCD, living inside the cluster, continuously makes reality match git.

**Read `PRIMER.md` first.** GitOps is a genuinely new idea and the tooling makes no sense until the idea does. `architecture.svg` shows the shape: notice there is no arrow from Jenkins to the cluster.

You will reuse the ShopFlow system from Project 6, so there is no new application to learn. The only thing that changes is how it gets deployed, which is exactly the lesson.

## Prerequisites

- Project 6 Phase 1 is working: the EKS cluster, RDS, SQS, ECR images, and the AWS Load Balancer Controller all exist, and you can place an order.
- `kubectl` and `helm` installed, and your kubeconfig points at the cluster.
- A GitHub account where you can create a second, separate repository.

Cost warning, as always: the cluster, database, and load balancer bill by the hour. ArgoCD itself is cheap, but the platform under it is not. Tear down when you finish (see Cleanup).

## What is in this folder

```
PRIMER.md                     read this first
architecture.svg              the push-to-pull picture (the core idea)
aws-architecture.png          the full AWS architecture for this project
COMMANDS.md                   the ArgoCD CLI and operations lab (do this after Step 5)
argocd/                       the ArgoCD Application definitions
gitops-repo/                  the manifests that become YOUR GitOps repository
Jenkinsfile.gitops            the pipeline that commits instead of deploying
ASSIGNMENT.md                 what to submit
```

## Step 1: Install ArgoCD in the cluster

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl get pods -n argocd -w      # wait until all pods are Running
```

Get the admin password and open the UI:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo

kubectl port-forward svc/argocd-server -n argocd 8090:443
```

Open `https://localhost:8090` (accept the certificate warning) and log in as `admin`. The UI will be empty. That is correct: ArgoCD does not know about anything yet.

## Step 2: Create your GitOps repository

This is the heart of the project. Create a **new, separate** GitHub repository, for example `shopflow-gitops`. It holds only manifests, no application code.

Copy the `gitops-repo/` contents into it:

```bash
cp -r gitops-repo/* /path/to/your/shopflow-gitops/
cd /path/to/your/shopflow-gitops
```

Now fill in your own values before the first commit:

- In `apps/shopflow/config.yaml`, set your RDS endpoint host.
- In each of `catalog.yaml`, `orders.yaml`, `notifications.yaml`, `storefront.yaml`, replace `REPLACE_REGISTRY` with your ECR registry (`<account>.dkr.ecr.<region>.amazonaws.com`).

Then push:

```bash
git init && git add . && git commit -m "initial desired state"
git branch -M main
git remote add origin https://github.com/<you>/shopflow-gitops.git
git push -u origin main
```

## Step 3: Carry over the database secret

ArgoCD manages what is in git, and your database password must never be in git. Create it directly in the target namespace, once:

```bash
kubectl create namespace shopflow
kubectl -n shopflow create secret generic db-credentials \
  --from-literal=username=shopflow \
  --from-literal=password='YOUR_DB_PASSWORD'
```

Pause on this: it is a real design question, not a footnote. Git is the source of truth for everything **except** secrets. Where secrets should live is one of the questions you must answer in your report.

## Step 4: Point ArgoCD at your repository

Edit `argocd/application-shopflow.yaml` and set `repoURL` to your GitOps repository. Then:

```bash
kubectl apply -f argocd/application-shopflow.yaml
```

Now watch the UI. ArgoCD will find your repo, see the manifests, notice the cluster does not match, and (because `automated` sync is on) apply them. Within a minute or two the app should go **Synced** and **Healthy**.

```bash
kubectl get application shopflow -n argocd
kubectl get pods -n shopflow
```

You just deployed without running a single `kubectl apply` for the app. You committed, and the cluster made itself match.

Get the URL and confirm the store works:

```bash
kubectl get ingress shopflow -n shopflow
```

## Step 5: Deploy by committing

Change something in git and watch the cluster follow. In your GitOps repo, edit `apps/shopflow/catalog.yaml` and change `replicas: 2` to `replicas: 3`. Commit and push.

```bash
git commit -am "scale catalog to 3" && git push
kubectl get pods -n shopflow -w
```

A third catalog pod appears, with nobody running a deploy. **That commit was the deploy.**

Now roll it back the GitOps way:

```bash
git revert HEAD && git push
```

The pod goes away. Your deploy history and your rollback mechanism are just git.

## Step 5b: Learn the ArgoCD CLI and operations

Now work through `COMMANDS.md`. It installs the `argocd` CLI and walks the commands you will actually use at work: inspecting apps, diffing git against the cluster, syncing and refreshing, rolling back, and patching. It also has you patch a live deployment and watch self-heal revert it, which teaches the model better than any explanation.

## Step 6: Wire Jenkins to commit instead of deploy

Open `Jenkinsfile.gitops`. Everything up to `Push to ECR` is the pipeline you already know. The old deploy stage is gone, replaced by `Update GitOps repo`, which clones the GitOps repo, rewrites the image tag, and commits.

To use it:

1. Add a Jenkins credential `gitops-repo` (username plus a GitHub token that can push to the GitOps repo).
2. Set `ECR_ACCOUNT` and `GITOPS_REPO` in the file.
3. Create a pipeline job for a service and run it.

Watch what happens: Jenkins finishes and reports success, having never touched the cluster. Then, a moment later, ArgoCD notices the commit and rolls out the new image. Two independent systems, connected only by git.

**Remove the cluster credentials from Jenkins afterwards** and prove the pipeline still works. That is the security payoff, and it is one of your deliverables.

## Step 7 (optional): Manage the platform itself

Apply `argocd/application-monitoring.yaml` to have ArgoCD manage the Prometheus and Grafana stack too. Now your monitoring tooling is also declared in git. Try uninstalling it by hand and watch ArgoCD reinstall it.

## Troubleshooting

- **App stuck `OutOfSync` and never syncs.** `automated` sync may be off, or ArgoCD cannot read the repo. Check the Application's status in the UI, and confirm `repoURL` and `path` are right. For a private repo you must add credentials in ArgoCD (Settings, Repositories).
- **`Synced` but `Degraded`.** Git was applied correctly, but the pods are unhealthy. That is an app problem, not a GitOps problem: `kubectl -n shopflow describe pod <pod>` and read the logs. Usually a wrong image tag or a missing secret.
- **Pods `CreateContainerConfigError`.** The `db-credentials` secret is missing from the `shopflow` namespace. Redo Step 3.
- **Your change does not appear.** ArgoCD polls roughly every three minutes by default. Hit Refresh in the UI, or set up a webhook.
- **You edited the cluster by hand and it snapped back.** That is `selfHeal` doing its job. Change git instead.

## Cleanup

```bash
kubectl delete -f argocd/application-shopflow.yaml    # removes the app it created
kubectl delete namespace argocd
```

Then tear down the Project 6 infrastructure (`terraform destroy`) if you are finished with it.

## Deliverable

Complete the challenges in `ASSIGNMENT.md` and write the report. The report matters more than the working cluster here: this project is about understanding a model, and you will be asked to explain and defend it, not just show a screenshot.
# project-7-gitops-argocd
