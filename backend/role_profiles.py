import re
from dataclasses import dataclass, replace
from typing import Tuple


@dataclass(frozen=True)
class Competency:
    key: str
    label: str
    pattern: re.Pattern
    essential: bool
    action: str
    action_detail: str
    timeframe: str
    effort: str
    cv_line: str


@dataclass(frozen=True)
class RoleProfile:
    role_id: str
    title: str
    family: str
    title_pattern: re.Pattern
    signal_pattern: re.Pattern
    levels: Tuple[str, ...]
    competencies: Tuple[Competency, ...]
    benchmark: str
    writing_focus: str
    credential: str = ""


def _p(expr: str) -> re.Pattern:
    return re.compile(expr, re.I)


def _c(key, label, expr, essential, action, detail, timeframe, effort, cv_line) -> Competency:
    return Competency(key, label, _p(expr), essential, action, detail, timeframe, effort, cv_line)


def _optional(comp: Competency) -> Competency:
    return replace(comp, essential=False)


ALL_LEVELS = ("student_graduate", "junior", "mid_level", "senior_lead", "career_changer", "executive")
EARLY_LEVELS = ("student_graduate", "junior", "career_changer")

PROGRAMMING = _c(
    "programming", "Programming language", r"\b(?:python|java|javascript|typescript|golang|kotlin|rust|ruby|php|laravel|django|rails|node(?:\.js)?)\b|\bc\+\+|\bc#", True,
    "Build one complete project in your main language",
    "Pick a real problem, finish it, and publish the code with a README that explains your design choices.",
    "Next 30 days", "Medium", "Built [project] in [language] to [solve what] for [who].",
)
APIS = _c(
    "apis", "API design", r"\b(?:rest(?:ful)?|graphql|grpc|apis?|endpoints?|fastapi|django|flask|spring|express)\b", True,
    "Design and document a small REST API",
    "Write the endpoints, validation and error responses, and publish example requests in the README.",
    "Next 30 days", "Medium", "Designed a REST API with [number] endpoints for [purpose], with validation and documented errors.",
)
DATA_STORAGE = _c(
    "data_storage", "Databases and data modelling", r"\b(?:sql|postgres(?:ql)?|mysql|sqlite|mongodb|redis|databases?|schemas?|quer(?:y|ies)|index(?:ed|es)?)\b", True,
    "Model a relational schema and write the queries yourself",
    "Back a project with PostgreSQL or SQLite, add a migration, and optimise at least one query you can time.",
    "Next 30 days", "Medium", "Modelled a [PostgreSQL] schema for [domain] and cut [query] time from [before] to [after].",
)
TESTING = _c(
    "testing", "Automated testing", r"\b(?:pytest|unit\s+tests?|integration\s+tests?|jest|junit|vitest|test\s+suites?|tdd|tests?)\b", True,
    "Add an automated test suite to your strongest project",
    "Cover the main paths and one awkward edge case. Record how many tests exist and any bug they caught.",
    "This week", "Low", "Added [number] automated tests covering [feature], catching [bug] before release.",
)
DELIVERY = _c(
    "delivery", "Deployment and tooling", r"\b(?:docker|kubernetes|ci/cd|github\s+actions|gitlab\s+ci|deploy(?:ed|ment)?|aws|azure|gcp|containeri[sz]ed)\b", False,
    "Containerise and deploy one project with a CI pipeline",
    "Add a Dockerfile and a workflow that runs the tests on every push, then deploy it somewhere a recruiter can open.",
    "Next 30 days", "Medium", "Containerised [project] and added CI that runs [number] tests on every push.",
)
PERFORMANCE = _c(
    "performance", "Performance and reliability", r"\b(?:latency|p95|p99|throughput|performance|profil(?:ed|ing)|cach(?:e|ing)|idempoten\w*|retr(?:y|ies)|uptime|reliab\w*)\b", False,
    "Measure one slow path before and after you fix it",
    "Time a slow endpoint, query or page, change one thing, and keep both numbers.",
    "Next 30 days", "Medium", "Reduced [operation] time from [before] to [after] by [technique].",
)
FRAMEWORK = _c(
    "framework", "Modern frontend framework", r"\b(?:react(?:\.js)?|vue(?:\.js)?|angular|svelte|next(?:\.js)?|nuxt)\b", True,
    "Ship a small app in one modern framework",
    "Build something with real state (forms, filtering, saved data) rather than a static tutorial page.",
    "Next 30 days", "Medium", "Built a [React] interface for [purpose] used by [who].",
)
VERSION_CONTROL = _c(
    "version_control", "Version control and code review", r"\b(?:git|github|gitlab|pull\s+requests?|code\s+reviews?)\b", True,
    "Put your projects on GitHub with a clean history",
    "Use branches and pull requests even on solo work, and pin your best two repositories.",
    "This week", "Low", "Maintained [project] on GitHub with [number] reviewed pull requests.",
)
STAKEHOLDERS = _c(
    "stakeholders", "Stakeholder communication", r"\b(?:stakeholders?|workshops?|presented|reported\s+to|liais\w*|business\s+users?|clients?)\b", True,
    "Present one piece of work to the people who use it",
    "Volunteer to walk a manager, client or society committee through a report or change, and note what they decided.",
    "Next 30 days", "Low", "Presented [analysis/change] to [audience], leading to [decision].",
)

PROFILES: Tuple[RoleProfile, ...] = (
    RoleProfile(
        "backend_engineer", "Backend Software Engineer", "Software engineering",
        _p(r"\b(?:back[\s-]?end|software|platform|api|python|java)\s+(?:engineer|developer)\b"),
        _p(r"\b(?:apis?|microservices?|backend|servers?|databases?|endpoints?|postgres(?:ql)?|sql)\b"),
        ALL_LEVELS,
        (replace(PROGRAMMING, label="Server-side language"), APIS, DATA_STORAGE, TESTING, DELIVERY, PERFORMANCE),
        "Shortlisted backend CVs show services you built or changed, the data stores behind them, how you tested them, and one or two measured results such as latency, failure rate or cost.",
        "Lead with the system you changed, then the technique, then the measured effect.",
    ),
    RoleProfile(
        "frontend_engineer", "Frontend Engineer", "Software engineering",
        _p(r"\b(?:front[\s-]?end|ui|web|react)\s+(?:engineer|developer)\b"),
        _p(r"\b(?:react|vue|angular|css|html|ui|ux|accessib\w*|components?)\b"),
        ALL_LEVELS,
        (
            FRAMEWORK,
            _c("markup", "HTML, CSS and responsive layout", r"\b(?:html5?|css3?|sass|scss|tailwind|responsive|flexbox)\b", True,
               "Rebuild one page responsively without a UI kit", "Hand-write the layout so you can explain every breakpoint.",
               "This week", "Low", "Implemented a responsive layout for [page] that works from mobile to desktop."),
            _c("js_ts", "JavaScript or TypeScript", r"\b(?:javascript|typescript)\b", True,
               "Convert one project to TypeScript", "Type the data models first, then the components.",
               "Next 30 days", "Medium", "Migrated [project] to TypeScript across [number] modules."),
            _optional(replace(TESTING, label="Frontend testing", pattern=_p(r"\b(?:jest|cypress|playwright|vitest|testing\s+library|unit\s+tests?|end-to-end\s+tests?)\b"))),
            _c("accessibility", "Accessibility", r"\b(?:accessib\w*|wcag|aria|screen\s+readers?|keyboard\s+navigation)\b", False,
               "Run an accessibility audit and fix what it finds", "Use Lighthouse or axe, fix contrast, labels and keyboard focus, and keep the before and after findings.",
               "This week", "Low", "Fixed [number] accessibility issues found by [tool] in [app]."),
            _c("fe_performance", "Page performance", r"\b(?:lighthouse|core\s+web\s+vitals|bundle\s+size|lazy[\s-]?load\w*|load\s+time|page\s+speed)\b", False,
               "Measure and cut a page's load time", "Record the Lighthouse score or load time, split the bundle or lazy-load, and measure again.",
               "Next 30 days", "Medium", "Cut [page] load time from [before] to [after] by [technique]."),
        ),
        "Strong frontend CVs show shipped interfaces, the framework and state decisions behind them, testing, accessibility, and measured load or usability improvements.",
        "Name the interface and its users, the technical decision you made, and what changed for the user.",
    ),
    RoleProfile(
        "fullstack_developer", "Full-Stack Developer", "Software engineering",
        _p(r"\b(?:full[\s-]?stack|web)\s+(?:engineer|developer)\b|\bfull[\s-]?stack\b"),
        _p(r"\b(?:react|node(?:\.js)?|apis?|databases?|frontend|backend)\b"),
        ALL_LEVELS,
        (
            replace(FRAMEWORK, key="fs_frontend"),
            replace(APIS, key="fs_backend", label="Backend and APIs", pattern=_p(r"\b(?:node(?:\.js)?|express|django|flask|fastapi|spring|rails|laravel|apis?|endpoints?)\b")),
            DATA_STORAGE, _optional(TESTING), DELIVERY,
        ),
        "Strong full-stack CVs show one or two products you took from interface to database to deployment, with your own part made clear.",
        "Show the whole path of a feature: interface, API, data, deployment, and the outcome.",
    ),
    RoleProfile(
        "graduate_software_engineer", "Graduate / Junior Software Engineer", "Software engineering",
        _p(r"\b(?:graduate|junior|intern|placement|trainee)\s+(?:software\s+)?(?:engineer|developer)\b|\bcomputer\s+science\b|\bsoftware\s+engineering\b"),
        _p(r"\b(?:computer\s+science|software|programming|projects?|github|algorithms?)\b"),
        EARLY_LEVELS,
        (
            PROGRAMMING,
            _c("project_delivery", "Finished projects", r"\b(?:built|developed|implemented|designed|shipped|deployed|created|delivered|released|launched)\b", True,
               "Finish one project end to end", "Scope it small enough to finish: tests, README, and a deployed link or demo video.",
               "Next 30 days", "Medium", "Built and deployed [project], which [does what], with [tests/users]."),
            VERSION_CONTROL, _optional(TESTING),
            _c("fundamentals", "Computer science fundamentals", r"\b(?:algorithms?|data\s+structures?|complexity|dijkstra|graphs?|recursion|concurren\w*)\b|\bA\*", False,
               "Write up one algorithmic problem you solved", "Explain the approach, the complexity, and what you compared it with.",
               "Next 30 days", "Low", "Implemented [algorithm] for [problem] and compared it with [alternative] on [dataset]."),
            _c("collaboration", "Working with others", r"\b(?:team(?:mates)?|pair(?:ed)?\s+programm\w*|code\s+reviews?|agile|scrum|society|hackathons?)\b", False,
               "Join one team project or hackathon", "Pick a role you can describe afterwards, such as owning the API or the tests.",
               "Next 90 days", "Medium", "Owned [part] of a [number]-person team project at [event/module]."),
        ),
        "Graduate CVs that get interviews show two or three finished projects with your own contribution, tests, and a link a recruiter can open, plus any internship or placement work.",
        "Put the project's purpose and your part first, then the hard problem you solved, then how you know it worked.",
    ),
    RoleProfile(
        "data_analyst", "Data Analyst", "Data and analytics",
        _p(r"\b(?:data|business\s+intelligence|bi|reporting|insights?|marketing)\s+analyst\b"),
        _p(r"\b(?:dashboards?|reporting|insights?|kpis?|metrics|analys(?:is|ed|ing))\b"),
        ALL_LEVELS,
        (
            _c("sql", "SQL", r"\bsql\b|\bpostgres(?:ql)?\b|\bmysql\b|\bbigquery\b|\bsnowflake\b", True,
               "Answer three business questions with SQL on a public dataset", "Use a real dataset, write the queries, and publish the questions, queries and answers.",
               "Next 30 days", "Medium", "Wrote SQL analyses of [dataset] answering [question], which showed [finding]."),
            _c("spreadsheets", "Spreadsheet analysis", r"\b(?:excel|google\s+sheets|spreadsheets?|pivot\s+tables?|vlookup|xlookup)\b", True,
               "Automate one report you produce by hand", "Rebuild it with pivot tables or lookups and note the time it now takes.",
               "This week", "Low", "Rebuilt the [weekly] [report] in Excel, cutting preparation from [before] to [after]."),
            _c("visualisation", "Dashboards and visualisation", r"\b(?:power\s*bi|tableau|looker|dashboards?|charts?|data\s+visuali[sz]ation)\b", True,
               "Publish one dashboard someone can open", "Build it in Power BI or Tableau Public on data you can share, and write what it shows.",
               "Next 30 days", "Medium", "Built a [Power BI] dashboard tracking [metric] for [audience]."),
            STAKEHOLDERS,
            _c("statistics", "Statistics and experiments", r"\b(?:statistic\w*|regression|a/b\s+test\w*|hypothes\w*|significan\w*|forecast\w*)\b", False,
               "Run and write up one statistical comparison", "Test a difference properly and explain what the result does and does not show.",
               "Next 90 days", "Medium", "Tested [hypothesis] on [data], finding [result] at [confidence]."),
            _c("analysis_code", "Python or R for analysis", r"\b(?:python|pandas|numpy|rstudio|tidyverse)\b", False,
               "Repeat one spreadsheet analysis in Python", "Use pandas so the analysis is repeatable, and keep the notebook public.",
               "Next 30 days", "Medium", "Automated [analysis] in Python (pandas), replacing [manual step]."),
        ),
        "Strong analyst CVs show the question asked, the data and tools used, the finding, and the decision it changed.",
        "Write each bullet as question, method, finding, and decision.",
        "Microsoft PL-300 (Power BI Data Analyst) or the Google Data Analytics Professional Certificate",
    ),
    RoleProfile(
        "data_scientist", "Data Scientist / ML Engineer", "Data and analytics",
        _p(r"\b(?:data\s+scientist|machine\s+learning|ml\s+engineer|ai\s+engineer)\b"),
        _p(r"\b(?:models?|machine\s+learning|predictions?|classifiers?|training)\b"),
        ALL_LEVELS,
        (
            replace(PROGRAMMING, label="Python", pattern=_p(r"\bpython\b")),
            _c("ml_libraries", "Machine-learning libraries", r"\b(?:scikit[\s-]?learn|sklearn|pytorch|tensorflow|keras|xgboost|lightgbm|hugging\s*face)\b", True,
               "Train one model with a standard library", "Use scikit-learn or PyTorch on a public dataset and keep a reproducible notebook.",
               "Next 30 days", "Medium", "Trained a [model type] in [library] on [dataset] to predict [target]."),
            _c("modelling", "Modelling", r"\b(?:models?|classif\w*|regression|predict\w*|neural\s+net\w*|trained|training|fine[\s-]?tun\w*)\b", True,
               "Frame one prediction problem properly", "State the target, the features, and why a model is better than a rule.",
               "Next 30 days", "Medium", "Framed [problem] as [task] and built a model for [use]."),
            _c("evaluation", "Evaluation against a baseline", r"\b(?:accuracy|precision|recall|f1|auc|roc|cross[\s-]?validat\w*|baselines?|evaluat\w*|benchmark\w*)\b", True,
               "Compare your model with a simple baseline", "Report the metric that matters for the problem and how far you beat the baseline.",
               "This week", "Low", "Improved [metric] from [baseline] to [result] against a [baseline method]."),
            _c("data_pipelines", "Data preparation and pipelines", r"\b(?:pandas|spark|pyspark|etl|pipelines?|airflow|feature\s+engineering)\b", False,
               "Build a repeatable data preparation step", "Turn notebook cleaning code into a script or pipeline you can rerun.",
               "Next 30 days", "Medium", "Built a [pipeline] that prepares [data] for [model]."),
            _c("ml_deployment", "Model deployment", r"\b(?:deployed|mlflow|serving|inference\s+api|production)\b", False,
               "Serve one model behind an API", "Wrap the model in a small API, containerise it, and document how to call it.",
               "Next 90 days", "Medium", "Deployed [model] behind an API serving [use]."),
        ),
        "Strong data-science CVs show the problem, the data, the model, the metric against a baseline, and whether it was used.",
        "State the problem and metric before the algorithm.",
    ),
    RoleProfile(
        "devops_cloud_engineer", "DevOps / Cloud Engineer", "Infrastructure",
        _p(r"\b(?:devops|cloud|site\s+reliability|sre|platform|infrastructure)\s+engineer\b"),
        _p(r"\b(?:infrastructure|deployments?|pipelines?|clusters?|cloud|incidents?)\b"),
        ALL_LEVELS,
        (
            _c("containers", "Containers and orchestration", r"\b(?:docker|kubernetes|k8s|helm|containeri[sz]\w*)\b", True,
               "Run a multi-container app locally and in a cluster", "Use Docker Compose, then deploy the same app to a small Kubernetes cluster.",
               "Next 30 days", "Medium", "Containerised [app] and deployed it to [Kubernetes] with [number] services."),
            _c("cicd", "CI/CD pipelines", r"\b(?:ci/cd|github\s+actions|gitlab\s+ci|jenkins|circleci|pipelines?)\b", True,
               "Build a pipeline that tests and deploys on every push", "Include a failing-test gate and a rollback step you have actually tried.",
               "This week", "Low", "Built a [GitHub Actions] pipeline that tests and deploys [app] on every push."),
            _c("cloud", "Cloud platform", r"\b(?:aws|azure|gcp|google\s+cloud|ec2|s3|lambda|cloud\s+run)\b", True,
               "Deploy one project on a cloud free tier", "Keep within free limits and write down what each service does in your setup.",
               "Next 30 days", "Medium", "Deployed [app] on [AWS] using [services]."),
            _c("iac", "Infrastructure as code", r"\b(?:terraform|cloudformation|ansible|pulumi|bicep|infrastructure\s+as\s+code)\b", True,
               "Rebuild your cloud setup in Terraform", "Destroy and recreate it from code to prove the code is complete.",
               "Next 30 days", "Medium", "Defined [environment] in Terraform, recreating it from scratch in [time]."),
            _c("observability", "Monitoring and incidents", r"\b(?:prometheus|grafana|datadog|monitoring|alerting|observability|logging|on[\s-]?call|incidents?)\b", False,
               "Add monitoring and one alert to a running service", "Pick a meaningful signal such as error rate and test that the alert fires.",
               "Next 30 days", "Low", "Added [Prometheus/Grafana] monitoring and alerting for [service]."),
            _c("scripting", "Scripting and Linux", r"\b(?:bash|shell\s+script\w*|powershell|linux|python)\b", False,
               "Automate one repetitive operations task", "Write a script for something you do by hand and note the time saved.",
               "This week", "Low", "Automated [task] with a [Bash] script, saving [time] per [period]."),
        ),
        "Strong DevOps CVs show pipelines and infrastructure you built, the scale they run at, incidents you handled, and reliability or cost results.",
        "Describe the system, the automation you added, and the reliability, speed or cost effect.",
        "AWS Certified Cloud Practitioner or Certified Kubernetes Administrator (CKA)",
    ),
    RoleProfile(
        "customer_service_retail", "Customer Service / Retail Team Member", "Customer and retail",
        _p(r"\b(?:retail|customer\s+service|store|shop|cashier|barista|front\s+of\s+house|sales\s+(?:assistant|associate|advisor))\b"),
        _p(r"\b(?:customers?|tills?|stock|stores?|shops?|sales|shifts?)\b"),
        ALL_LEVELS,
        (
            _c("customer_care", "Customer service", r"\bcustomers?\b|\bclients?\b|\bguests?\b", True,
               "Start noting customer outcomes you handle", "Keep a weekly note of compliments, resolved problems and repeat customers so you have specifics later.",
               "This week", "Low", "Handled around [number] customers per shift, with [feedback/result]."),
            _c("payments", "Tills and cash handling", r"\b(?:tills?|cash(?:ing\s+up)?|point\s+of\s+sale|pos\s+system|card\s+payments?|reconcil\w*)\b", True,
               "Ask to take on cashing up or reconciliation", "Responsibility for money is concrete evidence of trust.",
               "Next 30 days", "Low", "Reconciled the till each [shift] with [accuracy/result]."),
            _c("resolution", "Resolving complaints and problems", r"\b(?:complaints?|customer\s+(?:issues?|queries|problems?)|refunds?\s+(?:and|or)\s+exchanges?|escalat\w*|resolv\w*)\b", True,
               "Write down how you resolve the next difficult customer", "Record the problem, what you did, and the result, so you have a real example for interviews.",
               "This week", "Low", "Resolved [type of complaint] by [action], keeping [customer/result]."),
            _c("sales", "Sales and targets", r"\b(?:sales|targets?|upsell\w*|conversion|basket|promotions?)\b", False,
               "Ask your manager for your sales or target figures", "Many stores track these; knowing your figure turns a duty into a result.",
               "Next 30 days", "Low", "Achieved [result] against a [weekly] target of [figure]."),
            _c("stock", "Stock and merchandising", r"\b(?:stock|inventory|replenish\w*|merchandis\w*|deliveries|stock[\s-]?takes?)\b", False,
               "Volunteer for a stock take or display change", "It gives you a scoped task with a visible result.",
               "Next 30 days", "Low", "Led [stock take/display change] for [area], [result]."),
            _c("teamwork", "Teamwork and extra responsibility", r"\b(?:team|colleagues?|shifts?|rotas?|trained\s+(?:new\s+)?(?:staff|starters|colleagues)|key[\s-]?holder|opening|closing)\b", False,
               "Ask to train a new starter or become a key-holder", "Extra responsibility is what separates you from other applicants with the same job title.",
               "Next 90 days", "Medium", "Trained [number] new starters on [tasks]."),
        ),
        "Strong retail and customer CVs show volume handled, results against targets, problems resolved, and responsibility beyond the basic role such as key-holding or training.",
        "Replace duties with what you handled, how much, and what happened.",
    ),
    RoleProfile(
        "operations_admin", "Operations / Administrative Coordinator", "Business and operations",
        _p(r"\b(?:operations|office|admin(?:istrative|istrator)?|executive\s+assistant|personal\s+assistant)\b"),
        _p(r"\b(?:schedul\w*|process(?:es)?|admin\w*|records?|logistics|operations)\b"),
        ALL_LEVELS,
        (
            _c("scheduling", "Scheduling and logistics", r"\b(?:schedul\w*|rotas?|calendars?|diar(?:y|ies)|bookings?|logistics|appointments?)\b", True,
               "Take ownership of one schedule or rota", "Owning it end to end gives you something specific to describe.",
               "Next 30 days", "Low", "Managed the [rota/schedule] for [number] people, [result]."),
            _c("process", "Process improvement", r"\b(?:procedures?|streamlin\w*|(?:admin\w*|office|approval|onboarding|invoic\w*|booking)\s+(?:process(?:es)?|workflows?)|(?:improved|redesigned|automated|simplified)\s+(?:the\s+)?(?:process|procedure|workflow)\w*)\b", True,
               "Fix one slow or error-prone process and time it", "Measure how long it takes now, change it, and measure again.",
               "Next 30 days", "Medium", "Redesigned [process], cutting it from [before] to [after]."),
            _c("office_tools", "Office and business tools", r"\b(?:excel|spreadsheets?|crm|sap|salesforce|microsoft\s+office|google\s+workspace|sharepoint)\b", True,
               "Learn one tool to a level you can demonstrate", "For Excel, that means lookups, pivot tables and a small automated report.",
               "Next 30 days", "Low", "Built a [tracker/report] in [Excel] used by [team]."),
            _c("records", "Records and compliance", r"\b(?:records?|documentation|minutes|filing|compliance|invoices?|data\s+entry)\b", False,
               "Document one process so others can follow it", "A written procedure is evidence you can point to.",
               "This week", "Low", "Wrote the [procedure] now used by [team]."),
            _c("liaison", "Working with suppliers and clients", r"\b(?:stakeholders?|suppliers?|clients?|liais\w*|vendors?|contractors?)\b", False,
               "Become the contact for one supplier or client", "Note the issues you handle and how they were resolved.",
               "Next 90 days", "Medium", "Managed day-to-day contact with [number] suppliers, resolving [issue]."),
        ),
        "Strong operations CVs show what you kept running, at what volume, and the processes you made faster or more accurate.",
        "Show the volume you handled and the time or errors you removed.",
        "Microsoft Office Specialist: Excel Associate",
    ),
    RoleProfile(
        "business_analyst", "Business Analyst", "Business and operations",
        _p(r"\b(?:business|systems|product)\s+analyst\b"),
        _p(r"\b(?:requirements?|stakeholders?|user\s+stor(?:y|ies)|process\s+maps?)\b"),
        ALL_LEVELS,
        (
            _c("requirements", "Requirements and user stories", r"\b(?:requirements?|user\s+stor(?:y|ies)|acceptance\s+criteria|specifications?)\b", True,
               "Write requirements for one real change", "Turn a request at work or in a society into user stories with acceptance criteria.",
               "Next 30 days", "Low", "Gathered requirements for [change] and wrote [number] user stories with acceptance criteria."),
            STAKEHOLDERS,
            _c("process_mapping", "Process mapping", r"\b(?:process\s+maps?|process\s+mapping|bpmn|as[\s-]is|to[\s-]be|workflows?|swim\s*lanes?)\b", True,
               "Map one process as it is and as it should be", "Draw both versions and quantify the difference in steps or time.",
               "Next 30 days", "Low", "Mapped [process] and proposed a version with [number] fewer steps."),
            _c("ba_data", "Data analysis", r"\b(?:sql|excel|power\s*bi|tableau|data\s+analysis)\b", False,
               "Back one recommendation with data", "Use SQL or Excel to size the problem before proposing the fix.",
               "Next 30 days", "Medium", "Sized [problem] at [figure] using [SQL/Excel], supporting [decision]."),
            _c("agile", "Agile delivery", r"\b(?:agile|scrum|jira|sprints?|backlogs?|confluence)\b", False,
               "Work in a sprint-based team or run one yourself", "Keep the backlog and note what was delivered.",
               "Next 90 days", "Medium", "Maintained the backlog for [team] over [number] sprints."),
        ),
        "Strong business-analyst CVs show the problem, the stakeholders, the requirements or process change, and the measurable result.",
        "Name the problem and the stakeholders, then the change you defined and what it achieved.",
        "BCS Foundation Certificate in Business Analysis",
    ),
    RoleProfile(
        "project_coordinator", "Project Coordinator / Junior Project Manager", "Business and operations",
        _p(r"\b(?:project\s+(?:coordinator|manager|officer|administrator)|scrum\s+master|delivery\s+manager)\b"),
        _p(r"\b(?:milestones?|deadlines?|timelines?|project\s+plans?|stakeholders?)\b"),
        ALL_LEVELS,
        (
            _c("planning", "Planning and timelines", r"\b(?:plans?|planning|timelines?|milestones?|schedules?|gantt|roadmaps?)\b", True,
               "Plan one project with milestones and track it", "A society event, a home project or a work change all count if you track it.",
               "Next 30 days", "Low", "Planned [project] across [number] milestones and delivered by [date]."),
            STAKEHOLDERS,
            _c("pm_delivery", "Delivering on time", r"\b(?:delivered|launched|on\s+time|deadlines?|go[\s-]live|rolled\s+out)\b", True,
               "See one piece of work through to launch", "Note the deadline, what nearly stopped it, and how you kept it on track.",
               "Next 90 days", "Medium", "Delivered [project] [on time/under budget] despite [constraint]."),
            _c("risk", "Risks and issues", r"\b(?:risks?|issue\s+logs?|raid|mitigat\w*|dependenc\w*)\b", False,
               "Keep a risk and issue log for your next project", "Record each risk, its owner, and what you did.",
               "This week", "Low", "Ran the risk log for [project], resolving [number] issues before launch."),
            _c("methodology", "Delivery methods", r"\b(?:agile|scrum|prince2|waterfall|kanban|jira)\b", False,
               "Learn one delivery method and use it", "Applying Scrum or Kanban on a real project beats a certificate alone.",
               "Next 30 days", "Low", "Ran [project] using [Kanban], tracking [number] items to completion."),
            _c("budget", "Budget and cost", r"\b(?:budgets?|costs?|spend|forecast\w*)\b", False,
               "Ask to track the budget on a small project", "Even a small budget gives you a concrete responsibility.",
               "Next 90 days", "Medium", "Tracked a [£ amount] budget for [project], finishing [result]."),
        ),
        "Strong project CVs show the scope and size of projects, your role, how you handled risks, and whether delivery hit time and budget.",
        "State scope, your role, the obstacle, and the delivery result.",
        "PRINCE2 Foundation or PMI CAPM",
    ),
    RoleProfile(
        "marketing_content", "Marketing / Content Executive", "Marketing",
        _p(r"\b(?:marketing|content|social\s+media|digital|seo|brand|communications)\s+(?:executive|assistant|coordinator|manager|specialist|officer)\b"),
        _p(r"\b(?:campaigns?|content|social\s+media|brand|audiences?|engagement)\b"),
        ALL_LEVELS,
        (
            _c("campaigns", "Campaigns", r"\b(?:campaigns?|launch\w*|promotions?)\b", True,
               "Run one small campaign with a goal", "For a society, side project or local business: set a goal, run it, and record the outcome.",
               "Next 30 days", "Medium", "Ran a [channel] campaign for [audience], reaching [result]."),
            _c("channels", "Marketing channels", r"\b(?:social\s+media|instagram|tiktok|linkedin|facebook|email\s+marketing|newsletters?|seo|ppc|google\s+ads|paid\s+social)\b", True,
               "Grow one channel you can show", "Pick one channel and post consistently for a month.",
               "Next 30 days", "Medium", "Grew [channel] from [before] to [after] followers in [period]."),
            _c("content", "Content creation", r"\b(?:content|copy(?:writing)?|blogs?|articles?|videos?|wrote|posts?)\b", True,
               "Build a small portfolio of published work", "Three to five pieces you wrote or made, with links.",
               "Next 30 days", "Low", "Wrote [number] [articles/posts] for [publication], averaging [engagement]."),
            _c("mkt_analytics", "Marketing analytics", r"\b(?:google\s+analytics|ga4|engagement|ctr|click[\s-]through|conversions?|open\s+rates?|impressions|reach|followers)\b", False,
               "Track results for everything you publish", "Use GA4 or platform analytics so each piece has a number.",
               "This week", "Low", "Improved [metric] from [before] to [after] by [change]."),
            _c("mkt_tools", "Marketing tools", r"\b(?:canva|hubspot|mailchimp|adobe|figma|wordpress|hootsuite|semrush)\b", False,
               "Learn one tool through a real piece of work", "Use the tool for the campaign above rather than a tutorial.",
               "Next 30 days", "Low", "Produced [assets] in [tool] for [campaign]."),
        ),
        "Strong marketing CVs show campaigns with goals, channels used, content produced, and the measured response.",
        "Give the goal, the channel, what you made, and the measured response.",
        "Google Analytics Certification (free via Google Skillshop)",
    ),
)

PROFILES_BY_ID = {profile.role_id: profile for profile in PROFILES}
