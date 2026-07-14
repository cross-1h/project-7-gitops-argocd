from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import ECR
from diagrams.aws.database import RDS
from diagrams.aws.integration import SQS
from diagrams.aws.network import ElbApplicationLoadBalancer
from diagrams.onprem.ci import Jenkins
from diagrams.onprem.gitops import ArgoCD
from diagrams.onprem.vcs import Github
from diagrams.onprem.monitoring import Prometheus, Grafana
from diagrams.onprem.client import Users
from diagrams.programming.framework import Spring, React

graph_attr = {
    "fontsize": "24",
    "labelloc": "t",
    "label": "Project 7: GitOps delivery with ArgoCD on AWS EKS\n(ArgoCD runs INSIDE the cluster and pulls from git)",
    "pad": "0.8", "splines": "spline", "nodesep": "0.8", "ranksep": "1.4", "bgcolor": "white",
}

node_attr = {"fontsize": "14"}

with Diagram("p7", filename="/home/claude/p7_aws2", show=False,
             direction="LR", graph_attr=graph_attr, node_attr=node_attr, outformat="png"):

    users = Users("Users")

    with Cluster("CI  (has NO cluster credentials)"):
        app_repo = Github("App repo\ncode + Jenkinsfile")
        jenkins = Jenkins("Jenkins\nbuild · test · scan")
        app_repo >> Edge(color="gray") >> jenkins

    with Cluster("GIT  (the single source of truth)"):
        gitops = Github("GitOps repo\nDESIRED STATE\n(manifests)")

    with Cluster("AWS Cloud"):
        ecr = ECR("ECR\nimages")

        with Cluster("EKS cluster"):

            with Cluster("argocd namespace  <<< THE AGENT"):
                argo = ArgoCD("ArgoCD\nobserve · compare · sync\n(runs forever)")

            with Cluster("shopflow namespace"):
                storefront = React("Storefront")
                orders = Spring("Orders")
                catalog = Spring("Catalog")
                notif = Spring("Notifications")

            with Cluster("monitoring namespace"):
                prom = Prometheus("Prometheus")
                graf = Grafana("Grafana")

        alb = ElbApplicationLoadBalancer("ALB")
        sqs = SQS("SQS")
        rds = RDS("RDS\nPostgreSQL")

    # ---- request path (thin gray) ----
    users >> Edge(color="gray") >> alb >> Edge(color="gray") >> storefront
    storefront >> Edge(label="REST", color="gray") >> orders
    orders >> Edge(label="REST", color="gray") >> catalog
    orders >> Edge(label="publish", color="gray") >> sqs
    sqs >> Edge(label="consume", color="gray") >> notif
    orders >> Edge(color="gray") >> rds
    catalog >> Edge(label="JDBC", color="gray") >> rds
    prom >> Edge(style="dotted", color="gray") >> graf

    # ---- the GitOps flow (bold, numbered) ----
    jenkins >> Edge(label="  1. push image  ", color="darkgreen", penwidth="2.5", fontcolor="darkgreen") >> ecr
    jenkins >> Edge(label="  2. commit new image tag  ", color="darkgreen", penwidth="3.0", style="bold", fontcolor="darkgreen") >> gitops
    argo >> Edge(label="  3. PULL desired state  ", color="blue", penwidth="3.0", style="bold", fontcolor="blue", dir="back") >> gitops
    argo >> Edge(label="  4. sync + self-heal  ", color="darkorange", penwidth="3.0", style="bold", fontcolor="darkorange") >> orders
    argo >> Edge(color="darkorange", penwidth="2.0", style="bold") >> prom
    ecr >> Edge(label="pull image", style="dashed", color="gray") >> orders

print("done")
