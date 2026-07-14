# Project 7 Assignment: GitOps with ArgoCD

**Due: [set your deadline]**

The README will get you to a working ArgoCD setup. That is the easy part, and it is not what is being graded. This project is about whether you understand the model. The challenges below are things a person who copied commands cannot do, and the report is where you show your thinking.

## Part A: Get it working

Follow the README until the ShopFlow app shows **Synced** and **Healthy** in ArgoCD, and the store is reachable through the load balancer.

## Part B: The challenges

Do all five. Each needs evidence (a screenshot or terminal output) and a short written explanation of *what happened and why*.

**1. Deploy by commit.** Change the replica count of a service in git, push, and show the cluster following without any deploy command. Then `git revert` it and show the cluster rolling back. Explain what ArgoCD did between your push and the change appearing.

**2. Cause drift, and watch it heal.** With self-heal on, hand-edit the live cluster (`kubectl -n shopflow scale deployment/catalog-service --replicas=5`). Show ArgoCD detecting the drift and reverting it. Then explain: why is this desirable? Give one situation where it would be genuinely annoying, and say how you would handle that situation.

**3. Break the sync deliberately.** Commit a manifest with a bad image tag. Show that ArgoCD reports the app as **Synced** but **Degraded**, and explain in your own words why those two words are not a contradiction. This distinction is the most common ArgoCD interview question.

**4. Cut Jenkins off from the cluster.** Wire the `Jenkinsfile.gitops` pipeline so a build commits a new image tag instead of deploying. Then **delete the cluster credentials from Jenkins entirely** and run the pipeline again. Show that a release still reaches the cluster. Explain what security property you just gained, and what Jenkins can and cannot now do.

**5. Prune.** Delete a manifest from the GitOps repo, push, and show ArgoCD removing that resource from the cluster. Then explain what would have happened with `prune: false`, and why an orphaned resource is a real problem (think about cost and about security).

## Part C: The report

Submit a PDF, `Project7-Report-<YourName>.pdf`. It must include:

1. **Your own architecture diagram**, drawn by you, not the one provided. Show where the desired state lives, who pushes and who pulls, and where the trust boundary sits.

2. **The design-decision section.** Answer these properly, in your own words. Short, thought-through paragraphs, not a copied definition:
   - Why does GitOps use a pull model instead of pushing from the pipeline? Name the concrete benefit.
   - Where should secrets live, given that git is the source of truth but a password must never be committed? You created the database secret by hand in Step 3. Explain why that is unsatisfying, and describe a better approach.
   - What is the trade-off you accept with automated sync and self-heal? When would you turn them off?
   - Why are the application repo and the GitOps repo separate?

3. **Your troubleshooting log.** Every error you hit, what you thought it was, what it actually was, and how you fixed it. Be honest. A log with real failures scores higher than a suspiciously clean one.

4. **What you would do next.** Name one thing this setup still does not do well, and how you would fix it.

## Part D: The defense

You will demo this live for ten minutes: walk your architecture, trigger a deploy by commit, and answer questions. Be ready to explain any command you ran and any line of any manifest you submitted. If you cannot explain it, do not submit it.

## Grading (100 points)

- Working ArgoCD setup, app Synced and Healthy, store reachable: 15
- The five challenges, with evidence and explanations: 30
- Design-decision answers (the reasoning, not the vocabulary): 25
- Your own architecture diagram: 10
- Troubleshooting log: 10
- Live defense: 10

Note the shape of that: **only 15 points are for it working.** Most of the marks are for understanding it. That is deliberate.

## Submission

Reply to the assignment email with your GitOps repository link, your app repository link, your screenshots, and your report PDF.
