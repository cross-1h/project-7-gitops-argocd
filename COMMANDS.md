# ArgoCD Commands and Operations Lab

The README gets ArgoCD running and uses the web UI. This file is the hands-on operations lab: the `argocd` CLI, and the day-to-day commands you would actually run on the job. Work through it after the app is Synced.

Rule to hold on to as you go: **in GitOps, the CLI is for inspecting, diagnosing, and emergency action. It is not how you deploy.** Deploying is still a commit. Every time you use a command here that changes something, ask yourself whether git should have changed instead.

## 1. Install the ArgoCD CLI

Linux:

```bash
curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
sudo install -m 555 argocd /usr/local/bin/argocd
rm argocd
```

macOS: `brew install argocd`

Windows (PowerShell as admin), or download the `.exe` from the ArgoCD releases page:

```powershell
winget install -e --id Argoproj.ArgoCD
```

Verify:

```bash
argocd version --client
```

## 2. Log in from the CLI

Keep the port-forward running in one terminal:

```bash
kubectl port-forward svc/argocd-server -n argocd 8090:443
```

In another terminal:

```bash
PASS=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
argocd login localhost:8090 --username admin --password "$PASS" --insecure
```

Change the password, since the initial one is a bootstrap secret:

```bash
argocd account update-password
```

## 3. Inspect applications

```bash
argocd app list                      # all apps and their sync/health status
argocd app get shopflow              # full detail: every resource ArgoCD manages
argocd app resources shopflow        # just the resource tree
argocd app history shopflow          # every sync, with the git commit that caused it
```

`argocd app get` is the command you will use most. Read its output carefully: it shows each resource, whether it is in sync, and whether it is healthy. Those are the two different questions from the primer.

## 4. See the difference between git and the cluster

This is the single most useful ArgoCD command:

```bash
argocd app diff shopflow
```

It prints exactly what is different between the desired state in git and the live cluster. If the app is Synced, this prints nothing. Cause some drift and run it again, and it shows you precisely what someone changed by hand.

## 5. Sync, refresh, and prune

```bash
argocd app refresh shopflow          # re-read git NOW instead of waiting for the poll
argocd app sync shopflow             # apply the desired state now
argocd app sync shopflow --dry-run   # show what a sync would do, change nothing
argocd app sync shopflow --prune     # also delete resources removed from git
```

With automated sync on, you rarely run `sync` by hand. `refresh` is the one you will actually use, when you have pushed a commit and do not want to wait for the poll interval.

## 6. Roll back

Two ways, and the difference matters:

```bash
argocd app history shopflow          # find the revision id you want
argocd app rollback shopflow 3       # roll the cluster back to that sync
```

This is the **emergency** rollback: fast, but now the cluster no longer matches git, so ArgoCD will report OutOfSync (and with self-heal on, it will fight you and roll forward again).

The **correct** rollback is in git:

```bash
git revert <bad-commit> && git push
```

Now the desired state itself has changed, and the cluster follows. Use `argocd app rollback` to stop the bleeding in an incident, then immediately fix git so the two agree. Being able to explain that distinction is worth marks.

## 7. Patching: the imperative escape hatch

You will be asked to patch things at work, so learn it, and learn why it is dangerous here.

Patch a live Kubernetes resource directly:

```bash
kubectl -n shopflow patch deployment catalog-service \
  -p '{"spec":{"replicas":4}}'
```

Now watch what happens:

```bash
argocd app diff shopflow      # shows your patch as a difference from git
kubectl -n shopflow get deployment catalog-service -w
```

With `selfHeal: true`, ArgoCD reverts your patch within a couple of minutes. **Your patch loses.** That is not a bug; it is the whole product working. Git said 2 replicas, so the cluster gets 2 replicas.

The lesson: in a GitOps cluster, `kubectl patch` and `kubectl edit` are for diagnosis and emergencies only. If you want a change to persist, change git.

ArgoCD can also patch its own Application objects, which is a legitimate use because the Application is configuration, not workload:

```bash
# temporarily turn OFF self-heal (for example, to debug an incident)
kubectl -n argocd patch application shopflow --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":false}}}}'

# turn it back on
kubectl -n argocd patch application shopflow --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":true}}}}'
```

Do this, patch a deployment again, and confirm your change now survives. Then turn self-heal back on and watch it revert. That pair of experiments teaches self-heal better than any explanation.

## 8. Create an application from the CLI

You created the app declaratively (a YAML file). You can also do it imperatively:

```bash
argocd app create shopflow-cli \
  --repo https://github.com/<you>/shopflow-gitops.git \
  --path apps/shopflow \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace shopflow \
  --sync-policy automated \
  --self-heal --auto-prune
```

Then ask yourself the GitOps question: this app now exists, but **where is it written down?** Nowhere in git. If your cluster is destroyed, this app is gone, while the one defined in `application-shopflow.yaml` can be recreated from the file. That is why the declarative version is the right one, and it is exactly the argument for the App-of-Apps pattern below.

Clean it up:

```bash
argocd app delete shopflow-cli
```

## 9. Watch the reconciliation loop

```bash
argocd app get shopflow --refresh
kubectl get application shopflow -n argocd -w
kubectl logs -n argocd deploy/argocd-application-controller -f | grep shopflow
```

The controller logs are where you see reconciliation happening in real time. Push a commit and watch the log line appear.

## 10. Useful diagnostics

```bash
argocd app logs shopflow                       # logs from the app's pods, through ArgoCD
argocd app logs shopflow --container orders-service
argocd repo list                               # repositories ArgoCD knows about
argocd repo add https://github.com/<you>/shopflow-gitops.git \
  --username <user> --password <token>         # needed for a PRIVATE repo
argocd cluster list                            # clusters ArgoCD manages
argocd app set shopflow --sync-policy none     # turn automated sync off
```

`argocd repo add` is the fix for the most common failure: a private GitOps repo that ArgoCD cannot read.

## 11. App of Apps (the pattern worth knowing)

Right now you apply each Application by hand with `kubectl apply`. That does not scale, and those Applications are not in git.

The **App of Apps** pattern fixes this: you create one "root" Application whose git path contains *other* Application manifests. ArgoCD syncs the root, which creates all the children, which deploy the workloads. Now even your ArgoCD configuration is version-controlled, and a fresh cluster can be fully rebuilt by pointing ArgoCD at one repository.

Try it: put `application-shopflow.yaml` and `application-monitoring.yaml` in a folder in your GitOps repo, then create a root Application pointing at that folder. Deleting and rebuilding your whole platform becomes one command.

## What to be able to explain afterwards

- The difference between `argocd app sync`, `argocd app refresh`, and a `git push`.
- Why `argocd app rollback` and `git revert` are both rollbacks, and when to use each.
- Why `kubectl patch` does not stick, and why that is a feature.
- Why an app created with `argocd app create` is worse than one defined in a YAML file in git.
