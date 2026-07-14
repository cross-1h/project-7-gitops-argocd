# Project 7 Challenges Log

This file is a simple place to record the problems encountered while working through the ArgoCD and GitOps project, how each issue was resolved, and where screenshots or images can be attached later.

## How to Use This File

- Add one section for each challenge you run into.
- Write the problem in plain language.
- Explain the fix in simple terms.
- Keep abbreviations written out in full the first time they appear, for example: Kubernetes (K8s), Amazon Elastic Container Registry (ECR), Amazon Relational Database Service (RDS).
- Replace the image placeholders with your own screenshots when ready.

---

## 1. ArgoCD pods were not fully ready

### Challenge
When I ran the ArgoCD installation commands, the pods did not all come up immediately. One of the controller pods was restarting and showing errors during startup.

Image placeholder:
![ArgoCD pod startup issue](images/argocd-pod-startup-issue.png)

### What it meant in simple terms
ArgoCD was trying to start, but one part of it could not finish launching correctly. It was like starting a team of workers, but one worker kept crashing before the job was complete.

### What I did to fix it
I checked the pod status and inspected the logs for the failing controller. The issue turned out to be related to the ApplicationSet custom resource definition (CRD), which was missing or not being registered correctly.

### Resolution
I reapplied the ArgoCD installation manifest and ensured the ApplicationSet custom resource definition was created and established successfully.

Resolution commands:
```bash
kubectl apply --server-side --force-conflicts -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=Established crd/applicationsets.argoproj.io --timeout=180s
```

### Result
The ArgoCD pods became healthy and the controller stopped restarting.

Verification command:
```bash
kubectl get pods -n argocd
kubectl get crd applicationsets.argoproj.io
```

Verification image placeholder:
![ArgoCD pods healthy](images/argocd-pods-healthy.png)

---

## 2. ApplicationSet controller kept crashing

### Challenge
The ApplicationSet controller pod kept restarting with errors about not finding the ApplicationSet resource.

Image placeholder:
![ApplicationSet controller crash](images/applicationset-controller-crash.png)

### What it meant in simple terms
The controller was looking for a piece of Kubernetes configuration that had not been properly installed yet. It kept failing because the system did not recognize that resource.

### What I did to fix it
I verified the ApplicationSet custom resource definition and recreated it using a server-side apply approach to avoid the earlier installation issue.

### Resolution
The ApplicationSet custom resource definition was successfully created and became established.

Resolution commands:
```bash
kubectl apply --server-side --force-conflicts -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=Established crd/applicationsets.argoproj.io --timeout=180s
```

### Result
The ApplicationSet controller stopped crashing and stayed running.

Verification command:
```bash
kubectl get pods -n argocd
```

Verification image placeholder:
![ApplicationSet controller healthy](images/applicationset-controller-healthy.png)

---

## 3. GitOps repository setup

### Challenge
I needed to create a separate Git repository that would hold only the manifest files for ArgoCD to manage.

Image placeholder:
![GitOps repository setup](images/gitops-repo-setup.png)

### What it meant in simple terms
The application code was not going into this repository. Only the deployment instructions were going there, so ArgoCD could compare the cluster to what was declared in Git.

### What I did to fix it
I created a new local folder for the GitOps repository, copied the manifest files from the project’s GitOps folder into it, and initialized Git inside that folder.

### Resolution
The local repository was prepared and ready for Git commits and pushes to GitHub.

Resolution commands:
```bash
mkdir -p ~/shopflow-gitops
cp -r /Users/cross/techlearn/project-7-gitops-argocd/gitops-repo/* ~/shopflow-gitops/
cd ~/shopflow-gitops
git init
git add .
git commit -m "initial desired state"
```

### Result
The GitOps repository contained the manifests needed for ArgoCD to manage the application state.

Verification command:
```bash
git status
```

Verification image placeholder:
![GitOps repo ready](images/gitops-repo-ready.png)

---

## 4. Configuring the deployment values

### Challenge
The repository needed custom values such as the database endpoint host and the container registry address before the first commit.

Image placeholder:
![Config values updated](images/config-values-updated.png)

### What it meant in simple terms
The template files were there, but they needed my own environment-specific details so the deployment would point to the correct services.

### What I did to fix it
I updated the configuration files with the correct database endpoint and container registry values.

### Resolution
The manifest files were customized for my environment.

Resolution commands:
```bash
# No shell commands were needed; the values were edited directly in the manifest files.
```

### Result
The deployment definitions were ready to be committed and used by ArgoCD.

Verification check:
I reviewed the updated manifest files to confirm the placeholder values had been replaced.

Verification image placeholder:
![Config values verified](images/config-values-verified.png)

---

## 5. ArgoCD application pointing at the correct repository

### Challenge
ArgoCD needed to know where the GitOps repository was located so it could read the manifests.

Image placeholder:
![ArgoCD app repo configuration](images/argocd-app-repo-config.png)

### What it meant in simple terms
ArgoCD was like a worker who needed the correct address before it could fetch the instructions. Without the correct repository URL, it could not do its job.

### What I did to fix it
I updated the ArgoCD Application definition so it pointed to the new GitOps repository.

### Resolution
ArgoCD could now find the repository and begin reading the desired state from Git.

Resolution commands:
```bash
kubectl apply -f argocd/application-shopflow.yaml
```

### Result
The application was deployed and managed through GitOps.

Verification command:
```bash
kubectl get application shopflow -n argocd
```

Verification image placeholder:
![ArgoCD app synced](images/argocd-app-synced.png)

---

## 6. Secret handling for database credentials

### Challenge
The database password should not be stored in Git, but the application still needed access to it.

Image placeholder:
![Database secret created](images/database-secret-created.png)

### What it meant in simple terms
The deployment files could be public in Git, but sensitive information such as passwords had to stay outside Git and be created directly in the cluster.

### What I did to fix it
I created the database credentials secret in the target namespace directly using Kubernetes commands.

### Resolution
The application had the secret it needed without storing the password in Git.

Resolution commands:
```bash
kubectl create namespace shopflow
kubectl -n shopflow create secret generic db-credentials \
  --from-literal=username=shopflow \
  --from-literal=password='YOUR_DB_PASSWORD'
```

### Result
The application could connect to the database securely.

Verification command:
```bash
kubectl -n shopflow get secret db-credentials
```

Verification image placeholder:
![Database secret verified](images/database-secret-verified.png)

---

## 7. Storefront pods not becoming ready after sync

### Challenge
ArgoCD showed the app as Synced but Degraded, and the storefront deployment had pods that were Running but not Ready.

Image placeholder:
![Storefront degradation](images/storefront-degraded.png)

### What it meant in simple terms
The manifest was applied, but Kubernetes still considered the storefront Deployment unhealthy because the new pods were not passing their readiness checks.

### What I did to fix it
I inspected the storefront pod and found the container was actually listening on port 8080, while the Deployment and Service were configured to use port 80.

### Resolution
I updated the storefront manifest so the container port and readiness probe used port 8080, and the service targetPort also pointed to 8080.

Resolution commands:
```bash
# Edit apps/shopflow/storefront.yaml
# Set containerPort: 8080 and readinessProbe port: 8080
# Set Service targetPort: 8080
```

### Result
The storefront deployment could start healthy pods, and ArgoCD stopped reporting Degraded once the rollout completed.

Verification command:
```bash
kubectl get pods -n shopflow
kubectl get application shopflow -n argocd
```

Verification image placeholder:
![Storefront healthy](images/storefront-healthy.png)

---

## 8. RDS connection exhaustion and proxy setup

### Challenge
The catalog service started crashing in a `CrashLoopBackOff` because it could not open a JDBC connection to PostgreSQL. The raw RDS host was still being used in the app config, and the database reported connection slot exhaustion.

Image placeholder:
![Postgres connection exhaustion](images/postgres-connection-exhaustion.png)

### What it meant in simple terms
The app was trying to open too many connections directly to the database at once, and PostgreSQL was refusing new connections. The service could not start because it could not reach a stable database connection.

### What I did to fix it
- Added an AWS RDS Proxy in Terraform to pool and manage database connections.
- Created a dedicated proxy security group and attached it to the proxy.
- Created a Secrets Manager secret for the proxy credentials and attached it to the proxy auth configuration.
- Corrected the proxy IAM role trust policy from `rds-db.amazonaws.com` to `rds.amazonaws.com`.

### Resolution
The infrastructure was updated with an RDS Proxy and the proxy was configured in the same VPC and subnets as the database. This offloads connection handling from the RDS instance and reduces direct connection pressure.

Verification commands:
```bash
terraform plan -out=tfplan
TF_VAR_db_password='...secret...' terraform apply -auto-approve tfplan
```

### Result
The proxy was created successfully, and the application configuration was prepared to use the new proxy endpoint.

Verification image placeholder:
![RDS proxy created](images/rds-proxy-created.png)

---

## 9. Injecting the proxy endpoint into GitOps config

### Challenge
The GitOps config map was still pointing at the original RDS host instead of the new RDS Proxy endpoint.

Image placeholder:
![GitOps config update](images/gitops-config-update.png)

### What it meant in simple terms
ArgoCD was deploying the app with the old database host, so the new proxy infrastructure would not be used.

### What I did to fix it
Updated the `SPRING_DATASOURCE_URL` value in the GitOps config map to use `shopflow-db-proxy.proxy-...amazonaws.com:5432/shopflow`.

### Resolution
Both the local GitOps folder and the `gitops-repo` manifest were updated so the application would connect through RDS Proxy.

Verification commands:
```bash
kubectl get configmap shopflow-config -n shopflow -o yaml
kubectl get pods -n shopflow
```

### Result
The service began using the proxy endpoint once the updated config was applied.

Verification image placeholder:
![Proxy endpoint injected](images/proxy-endpoint-injected.png)

---

## 10. Reverting RDS instance size after proxy adoption

### Challenge
Initially, the RDS instance was upgraded to `db.t3.large`, but the goal was to rely on RDS Proxy for connection pooling and avoid unnecessary instance resizing.

Image placeholder:
![RDS instance revert](images/rds-instance-revert.png)

### What it meant in simple terms
The database was temporarily scaled up to avoid connection exhaustion, but once the proxy was in place, the instance could return to its original smaller size.

### What I did to fix it
- Reverted `instance_class` in Terraform from `db.t3.large` back to `db.t3.micro`.
- Re-ran `terraform plan` and applied the change with the same database password variable.

### Resolution
The Terraform apply completed cleanly, and the RDS instance was returned to `db.t3.micro` while still using RDS Proxy for connections.

Verification commands:
```bash
TF_VAR_db_password='...secret...' terraform apply -auto-approve tfplan
```

### Result
The infrastructure change was deployed and the app remained healthy.

Verification image placeholder:
![RDS scale revert success](images/rds-scale-revert-success.png)

---

## 11. CrashLoopBackOff resolved for catalog-service

### Challenge
One of the `catalog-service` pods kept failing with `CrashLoopBackOff` even though the other replicas were healthy.

Image placeholder:
![catalog service crashloop fixed](images/catalog-crashloop-fixed.png)

### What it meant in simple terms
A single replica was still trying to start with broken DB connectivity while the rest of the deployment had already recovered.

### What I did to fix it
- Verified the `shopflow-config` config map and `db-credentials` secret were correct.
- Confirmed the proxy DNS resolved inside the pod and that the proxy was reachable once the infrastructure changes completed.
- Reconciled the deployment state after the RDS proxy and instance revert were applied.

### Resolution
The failing replica recovered and the `shopflow` namespace pods became fully healthy.

Verification commands:
```bash
kubectl get pods -n shopflow
kubectl get application shopflow -n argocd
```

### Result
The `catalog-service` crashloop was resolved and the shopflow application was running as expected.

Verification image placeholder:
![shopflow pods healthy](images/shopflow-pods-healthy.png)
