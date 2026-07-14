# Primer: GitOps and ArgoCD

Read this before you touch the project. You have never done GitOps, and the whole point of this project is one idea. Once that idea clicks, the tooling is easy.

## The problem with what you have been doing

In Projects 4, 5, and 6 your pipeline ended with a deploy stage. Jenkins ran something like `kubectl apply` or `helm upgrade`, and the cluster changed. That is called a **push** model: the pipeline reaches into the cluster and pushes the change in.

It works, but it has real problems, and you have probably already felt some of them.

**Jenkins needs powerful credentials.** To deploy, your pipeline holds keys that let it change your production cluster. If Jenkins is compromised, so is production.

**Nobody knows what is actually running.** Someone runs `kubectl edit` at 2am to fix an incident and never tells anyone. Now the cluster does not match your manifests, and no one notices until the next deploy silently wipes the fix, or preserves a change nobody remembers making. This gap is called **drift**.

**There is no single source of truth.** To answer "what is deployed right now?" you have to go ask the cluster. The answer lives in the cluster, not anywhere you can review, diff, or roll back.

## The GitOps idea

GitOps flips it around. The rule is one sentence:

> **Git is the single source of truth for what should be running, and an agent inside the cluster continuously makes reality match git.**

You do not deploy. You **commit**. A change to the cluster is a change to a file in a git repository: a pull request, reviewed, merged. An agent living inside the cluster watches that repository, notices the difference, and applies it. That is a **pull** model: the cluster pulls its own desired state, rather than a pipeline pushing state in.

Three things fall out of this, and they are the reasons the industry moved this way:

- **Your deploy history is your git history.** Who changed production, when, why, and who approved it are all just the commit log. Rolling back is `git revert`.
- **Jenkins no longer needs cluster credentials.** The pipeline's job ends at "build the image and update a tag in a git repo." The agent inside the cluster does the deploying. The blast radius of a compromised pipeline shrinks enormously.
- **Drift gets detected and corrected.** The agent is always comparing the cluster to git. If someone hand-edits a deployment, the agent sees the cluster no longer matches git and can put it straight back. Your 2am `kubectl edit` gets reverted automatically, which sounds annoying until you realise it means the cluster can never quietly diverge from what is written down.

## ArgoCD, in plain terms

**ArgoCD is that agent.** It runs inside your Kubernetes cluster. You point it at a git repository and tell it which folder holds your manifests. From then on it does three things forever, in a loop:

1. **Observe.** Read the manifests in git (the *desired state*), and read what is actually in the cluster (the *live state*).
2. **Compare.** Are they the same? If not, ArgoCD marks the app **OutOfSync**.
3. **Act.** Apply the difference so the cluster matches git. This is called a **sync**.

That loop is called **reconciliation**, and it never stops. It is the whole product.

### The words you will see in the ArgoCD UI

- **Application:** ArgoCD's unit of work. It says "the manifests in *this repo*, at *this path*, belong in *this cluster and namespace*." You define it as a Kubernetes object, so even your ArgoCD config is in git.
- **Synced / OutOfSync:** does the cluster match git or not.
- **Healthy / Degraded / Progressing:** are the resulting workloads actually well (pods running, rollout complete).

Notice those are two different questions. An app can be **Synced but Degraded**: git was applied faithfully, but the pods are crashing (you committed a bad image tag). It can also be **OutOfSync but Healthy**: everything is running fine, but someone changed the cluster by hand and it no longer matches git.

- **Automated sync:** ArgoCD applies changes as soon as it sees them, with no human clicking Sync.
- **Self-heal:** if the live cluster drifts from git, put it back. This is what reverts the hand-edit.
- **Prune:** if you delete a manifest from git, delete the resource from the cluster. Without prune, deleted files leave orphans running.

## What actually changes in your pipeline

This is the part students find surprising, so read it twice.

Your Jenkins pipeline **stops deploying**. Its last step is no longer `kubectl apply` or `helm upgrade`. Instead:

1. Jenkins builds, tests, scans, and pushes the image to ECR (exactly as in Project 5 and 6), tagged with the build number.
2. Jenkins then **commits a one-line change to the GitOps repository**, updating the image tag in a manifest.
3. Jenkins is done. It never touches the cluster.
4. ArgoCD sees the new commit, syncs, and rolls out the new version.

So the deploy is triggered by a commit, not by a pipeline. If you want to roll back, you revert the commit and ArgoCD rolls the cluster back for you.

## Two repositories, and why

This trips people up. You end up with:

- **The application repository:** your source code, `Dockerfile`, `Jenkinsfile`. What the app *is*.
- **The GitOps repository:** the Kubernetes manifests. What should be *running*.

They are separate because they change for different reasons and are reviewed by different people. A developer changing business logic touches the app repo. Someone changing replica counts, resource limits, or the image tag touches the GitOps repo. It also avoids an ugly loop where the pipeline commits to the same repo that triggers the pipeline.

In this project the GitOps repo is the `gitops-repo/` folder. You will push it to a repository of your own, and point ArgoCD at it.

## The one mental model to keep

Everything else is detail. Hold on to this:

> **You no longer tell the cluster what to do. You write down what you want, in git. The cluster's job is to go and become that.**

If you can explain that sentence, why it is safer than pushing, and what drift is, you understand GitOps better than most people who have used ArgoCD for a year.
