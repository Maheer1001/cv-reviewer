"""Shared building blocks for role profiles: the competency type and competencies reused across roles."""

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
    "programming", "Programming language",
    r"\b(?:python|java|javascript|typescript|golang|kotlin|swift|scala|rust|ruby|php|dart|lua)\b|\bc\+\+|\bc#", True,
    "Build one complete project in your main language",
    "Pick a real problem, finish it, and publish the code with a README that explains your design choices.",
    "Next 30 days", "Medium", "Built [project] in [language] to [solve what] for [who].",
)
APIS = _c(
    "apis", "API design",
    r"\b(?:rest(?:ful)?|graphql|grpc|apis?|endpoints?|fastapi|django|flask|spring|express|nestjs)\b", True,
    "Design and document a small REST API",
    "Write the endpoints, validation and error responses, and publish example requests in the README.",
    "Next 30 days", "Medium", "Designed a REST API with [number] endpoints for [purpose], with validation and documented errors.",
)
DATA_STORAGE = _c(
    "data_storage", "Databases and data modelling",
    r"\b(?:sql|postgres(?:ql)?|mysql|sqlite|mongodb|redis|databases?|schemas?|quer(?:y|ies)|index(?:ed|es)?)\b", True,
    "Model a relational schema and write the queries yourself",
    "Back a project with PostgreSQL or SQLite, add a migration, and optimise at least one query you can time.",
    "Next 30 days", "Medium", "Modelled a [PostgreSQL] schema for [domain] and cut [query] time from [before] to [after].",
)
TESTING = _c(
    "testing", "Automated testing",
    r"\b(?:pytest|unit\s+tests?|integration\s+tests?|jest|junit|vitest|test\s+suites?|tdd|tests?)\b", True,
    "Add an automated test suite to your strongest project",
    "Cover the main paths and one awkward edge case. Record how many tests exist and any bug they caught.",
    "This week", "Low", "Added [number] automated tests covering [feature], catching [bug] before release.",
)
DELIVERY = _c(
    "delivery", "Deployment and tooling",
    r"\b(?:docker|kubernetes|ci/cd|github\s+actions|gitlab\s+ci|deploy(?:ed|ment)?|aws|azure|gcp|containeri[sz]ed)\b", False,
    "Containerise and deploy one project with a CI pipeline",
    "Add a Dockerfile and a workflow that runs the tests on every push, then deploy it somewhere a recruiter can open.",
    "Next 30 days", "Medium", "Containerised [project] and added CI that runs [number] tests on every push.",
)
PERFORMANCE = _c(
    "performance", "Performance and reliability",
    r"\b(?:latency|p95|p99|throughput|performance|profil(?:ed|ing)|cach(?:e|ing)|idempoten\w*|retr(?:y|ies)|uptime|reliab\w*)\b", False,
    "Measure one slow path before and after you fix it",
    "Time a slow endpoint, query or page, change one thing, and keep both numbers.",
    "Next 30 days", "Medium", "Reduced [operation] time from [before] to [after] by [technique].",
)
FRAMEWORK = _c(
    "framework", "Modern frontend framework",
    r"\b(?:react(?:\.js)?|vue(?:\.js)?|angular|svelte|next(?:\.js)?|nuxt)\b", True,
    "Ship a small app in one modern framework",
    "Build something with real state (forms, filtering, saved data) rather than a static tutorial page.",
    "Next 30 days", "Medium", "Built a [React] interface for [purpose] used by [who].",
)
VERSION_CONTROL = _c(
    "version_control", "Version control and code review",
    r"\b(?:git|github|gitlab|pull\s+requests?|code\s+reviews?)\b", True,
    "Put your projects on GitHub with a clean history",
    "Use branches and pull requests even on solo work, and pin your best two repositories.",
    "This week", "Low", "Maintained [project] on GitHub with [number] reviewed pull requests.",
)
STAKEHOLDERS = _c(
    "stakeholders", "Stakeholder communication",
    r"\b(?:stakeholders?|workshops?|presented|reported\s+to|liais\w*|business\s+users?|clients?)\b", True,
    "Present one piece of work to the people who use it",
    "Volunteer to walk a manager, client or team through a change, and note what they decided.",
    "Next 30 days", "Low", "Presented [analysis/change] to [audience], leading to [decision].",
)
LINUX = _c(
    "linux", "Linux and the command line",
    r"\b(?:linux|ubuntu|debian|bash|shell\s+script\w*|systemd|cron)\b", True,
    "Do your day-to-day work in the terminal for a week",
    "Install, configure and troubleshoot something real over SSH, and write down the commands that mattered.",
    "This week", "Low", "Administered [system] over SSH, automating [task] with a shell script.",
)
SCRIPTING = _c(
    "scripting", "Scripting and automation",
    r"\b(?:python|bash|powershell|scripts?|automat\w*)\b", True,
    "Automate one task you currently do by hand",
    "A script that saves a measured amount of time is stronger evidence than a list of tools.",
    "This week", "Low", "Automated [task] with a [Python] script, saving [time] per [period].",
)
CLOUD = _c(
    "cloud", "Cloud platform",
    r"\b(?:aws|azure|gcp|google\s+cloud|ec2|s3|lambda|cloud\s+run|digitalocean)\b", True,
    "Deploy one project on a cloud free tier",
    "Keep within free limits and write down what each service does in your setup.",
    "Next 30 days", "Medium", "Deployed [app] on [AWS] using [services].",
)
NETWORKING = _c(
    "networking", "Networking fundamentals",
    r"\b(?:tcp/ip|dns|dhcp|subnets?|vlans?|routing|firewalls?|vpns?|osi)\b", True,
    "Build a small network and document it",
    "Even a home lab with two VLANs, DHCP and a firewall rule gives you something concrete to describe.",
    "Next 30 days", "Medium", "Built a lab network with [number] VLANs, DHCP and firewall rules between them.",
)
TROUBLESHOOTING = _c(
    "troubleshooting", "Troubleshooting method",
    r"\b(?:troubleshoot\w*|diagnos\w*|root[\s-]cause|debugg\w*|investigat\w*|isolat\w*)\b", True,
    "Write up one problem the way you actually solved it",
    "Symptom, what you checked, what you ruled out, the cause, and the fix. That narrative is what interviews test.",
    "This week", "Low", "Diagnosed [symptom] by [method], tracing it to [cause] and fixing it in [time].",
)
INCIDENTS = _c(
    "incidents", "Incidents and on-call",
    r"\b(?:incidents?|outages?|on[\s-]?call|postmortems?|sev[\s-]?[123]|war\s+rooms?)\b", False,
    "Keep a log of incidents you touch",
    "Note the impact, your part, the fix, and what changed afterwards so it cannot recur.",
    "Next 30 days", "Low", "Resolved a [severity] incident affecting [who] by [action], then added [safeguard].",
)
DOCUMENTATION = _c(
    "documentation", "Documentation",
    r"\b(?:document(?:ed|ation|ing)?|runbooks?|knowledge\s+base|readmes?|wikis?|confluence)\b", False,
    "Write one runbook for something only you know how to fix",
    "A page someone else has successfully followed is evidence of both the skill and the writing.",
    "This week", "Low", "Wrote the runbook for [system], now used by [team] for [task].",
)
SECURITY_BASICS = _c(
    "security_basics", "Security hygiene",
    r"\b(?:security|vulnerabilit\w*|owasp|authentication|encryption|least\s+privilege|hardening)\b", False,
    "Fix one real vulnerability and write it up",
    "Scan a project you own, fix the highest finding, and record what it was and why the fix works.",
    "Next 30 days", "Low", "Found and fixed [vulnerability] in [system], verified with [re-scan/test].",
)
AGILE = _c(
    "agile", "Agile delivery",
    r"\b(?:agile|scrum|kanban|jira|sprints?|stand[\s-]?ups?)\b", False,
    "Work in a sprint-based team, or run one yourself",
    "Note the cadence, your role, and what the team shipped.",
    "Next 30 days", "Low", "Delivered [number] stories across [number] sprints for [team/product].",
)
USER_FOCUS = _c(
    "user_focus", "Understanding users",
    r"\b(?:users?|usability|user\s+(?:research|interviews?|testing)|personas?|journeys?|feedback)\b", True,
    "Watch someone use something you made",
    "Three observed sessions will show you problems your own testing never will. Note what you changed.",
    "This week", "Low", "Watched [number] users attempt [task] and changed [thing] as a result.",
)
METRICS = _c(
    "metrics", "Measuring results",
    r"\b(?:metrics?|kpis?|analytics|measured|measuring|dashboards?|conversion|retention)\b", True,
    "Instrument one thing you ship",
    "Pick the number that shows whether it worked, record a baseline, and check it after release.",
    "Next 30 days", "Low", "Tracked [metric] for [feature], moving it from [before] to [after].",
)
HARDWARE_BUILD = _c(
    "hardware_build", "Building and prototyping hardware",
    r"\b(?:pcb|soldering|prototyp\w*|breadboard|3d\s+print\w*|cad|schematic|test\s+(?:rig|bench|fixture))\b", True,
    "Build one physical thing and record how you tested it",
    "A photo, a schematic and a test result beat a list of boards you have used.",
    "Next 30 days", "Medium", "Designed and built [device], verified by [test] against [requirement].",
)
EMBEDDED_CODE = _c(
    "embedded_code", "Firmware and embedded code",
    r"\b(?:firmware|embedded\s+(?:c|c\+\+|systems?)|microcontrollers?|rtos|arduino|stm32|esp32|raspberry\s+pi)\b|\bc\+\+", True,
    "Write firmware for a real board, not a simulator",
    "Blink is not enough: read a sensor, act on it, and handle the failure case.",
    "Next 30 days", "Medium", "Wrote firmware in [language] for [board] that [does what], handling [failure case].",
)
SENSORS_CONTROL = _c(
    "sensors_control", "Sensors and control",
    r"\b(?:sensors?|encoders?|imu|lidar|pid|control\s+loops?|kalman|actuators?|motors?|servos?)\b", True,
    "Close one control loop and tune it",
    "Read a sensor, drive an actuator, and record the before and after behaviour.",
    "Next 30 days", "Medium", "Closed a [PID] loop on [system], reducing [error] from [before] to [after].",
)
VISION_PERCEPTION = _c(
    "vision", "Computer vision and perception",
    r"\b(?:computer\s+vision|opencv|object\s+detection|cameras?|perception|image\s+processing)\b", False,
    "Make one perception component that works on your own data",
    "Detect, track or measure something real, and report accuracy against labelled examples.",
    "Next 90 days", "High", "Built [detector/tracker] for [what], reaching [accuracy] on [number] labelled examples.",
)
MOBILE_PLATFORM = _c(
    "mobile_platform", "A mobile platform",
    r"\b(?:android|ios|swift|swiftui|kotlin|flutter|react\s+native|jetpack\s+compose)\b", True,
    "Ship one app to a real device",
    "Install it on your own phone, use it for a week, and fix what annoys you.",
    "Next 30 days", "Medium", "Built a [platform] app for [purpose], installed and used on [devices].",
)
GAME_ENGINE = _c(
    "game_engine", "A game engine",
    r"\b(?:unity|unreal(?:\s+engine)?|godot|game\s+engine)\b", True,
    "Finish one small game and publish a build",
    "Scope it to one mechanic done well. A finished build beats a large unfinished project.",
    "Next 30 days", "Medium", "Built [game] in [engine] with [mechanic], published as a playable build.",
)
QA_PRACTICE = _c(
    "qa_practice", "Test design",
    r"\b(?:test\s+(?:plans?|cases|strategies|coverage)|edge\s+cases|boundary|regression|exploratory\s+testing)\b", True,
    "Write a test plan for one feature before you test it",
    "Cover the happy path, the boundaries, and the failures, then record what you actually found.",
    "This week", "Low", "Wrote [number] test cases for [feature], finding [number] defects including [example].",
)
AUTOMATION_TESTING = _c(
    "test_automation", "Test automation",
    r"\b(?:selenium|cypress|playwright|appium|automated\s+tests?|test\s+automation)\b", True,
    "Automate the tests you run by hand most often",
    "Pick the flow that regresses, automate it, and wire it into CI.",
    "Next 30 days", "Medium", "Automated [number] regression tests for [flow] with [tool], running in CI.",
)
BUG_HANDLING = _c(
    "bug_handling", "Bug reporting and triage",
    r"\b(?:bugs?|defects?|triage|reproduc\w*|severity|root[\s-]cause)\b", True,
    "Write bug reports a developer can act on first time",
    "Steps, expected, actual, environment, and a recording. Track how often yours come back with questions.",
    "This week", "Low", "Logged [number] defects for [product] with reproductions, [number] fixed in the same sprint.",
)
DATA_ANALYSIS = _c(
    "data_analysis", "Data analysis",
    r"\b(?:sql|excel|python|pandas|analys(?:is|ed|ing)|datasets?)\b", True,
    "Answer one real question with data and publish the working",
    "State the question, show the query or notebook, and write the answer in one sentence.",
    "Next 30 days", "Medium", "Analysed [dataset] to answer [question], finding [result].",
)
STATISTICS = _c(
    "statistics", "Statistics and experiments",
    r"\b(?:statistic\w*|regression|a/b\s+test\w*|hypothes\w*|significan\w*|forecast\w*|experiment\w*)\b", False,
    "Run and write up one statistical comparison",
    "Test a difference properly and explain what the result does and does not show.",
    "Next 90 days", "Medium", "Tested [hypothesis] on [data], finding [result] at [confidence].",
)
ML_CORE = _c(
    "ml_core", "Machine learning",
    r"\b(?:machine\s+learning|models?|classif\w*|regression|neural\s+net\w*|scikit[\s-]?learn|pytorch|tensorflow|trained|training)\b", True,
    "Train one model end to end on a problem you chose",
    "Own the data cleaning, the split, the baseline and the evaluation, not just the model call.",
    "Next 30 days", "Medium", "Trained a [model] to [predict what] on [dataset], beating a [baseline] by [margin].",
)
ML_EVAL = _c(
    "ml_eval", "Evaluation against a baseline",
    r"\b(?:accuracy|precision|recall|f1|auc|roc|cross[\s-]?validat\w*|baselines?|evaluat\w*|benchmark\w*)\b", True,
    "Compare your model with a simple baseline",
    "Report the metric that matters for the problem and how far you beat the obvious approach.",
    "This week", "Low", "Improved [metric] from [baseline] to [result] against a [baseline method].",
)
ML_DEPLOY = _c(
    "ml_deploy", "Model deployment",
    r"\b(?:deploy(?:ed|ment|ing)?|mlflow|serving|inference|production|pipelines?|monitoring)\b", False,
    "Serve one model behind an API and watch it",
    "Wrap it in a small API, containerise it, and log inputs and outputs so you can tell when it drifts.",
    "Next 90 days", "Medium", "Deployed [model] behind an API serving [use], with logging and a retraining trigger.",
)
LLM_SKILLS = _c(
    "llm", "Working with language models",
    r"\b(?:llms?|large\s+language\s+models?|gpt|claude|gemini|langchain|llamaindex|prompt\s+engineering|rag|embeddings?|vector\s+(?:databases?|stores?))\b", True,
    "Build one retrieval-augmented assistant on your own documents",
    "Measure answer quality against a set of questions you wrote by hand, and record the failures.",
    "Next 30 days", "Medium", "Built a RAG assistant over [documents], answering [number] test questions at [quality].",
)
ETL = _c(
    "etl", "Data pipelines",
    r"\b(?:etl|elt|pipelines?|airflow|dbt|spark|kafka|ingest\w*)\b", True,
    "Build one pipeline that runs unattended",
    "Schedule it, make it idempotent, and alert when it fails. Then leave it running.",
    "Next 30 days", "Medium", "Built a [daily] pipeline loading [source] into [warehouse], alerting on failure.",
)
WAREHOUSE = _c(
    "warehouse", "Data modelling and warehousing",
    r"\b(?:warehouse|data\s+lakes?|star\s+schemas?|dimensional|dbt|bigquery|snowflake|redshift)\b", True,
    "Model one business process as a star schema",
    "Define the grain, build the tables, and write the query the dashboard will run.",
    "Next 30 days", "Medium", "Modelled [process] as a star schema in [warehouse], serving [dashboard/team].",
)
VISUALISATION = _c(
    "visualisation", "Dashboards and visualisation",
    r"\b(?:power\s*bi|tableau|looker|dashboards?|charts?|data\s+visuali[sz]ation)\b", True,
    "Publish one dashboard someone actually uses",
    "Build it for a real question, and note who opens it and what decision it feeds.",
    "Next 30 days", "Medium", "Built a [Power BI] dashboard tracking [metric] for [audience].",
)
SAP_CORE = _c(
    "sap_core", "An SAP module",
    r"\b(?:sap(?:\s+(?:s/4hana|ecc|fi|co|mm|sd|pp|hcm|ewm|ehs|b1))?|s/4hana|abap)\b", True,
    "Document one end-to-end process you support in SAP",
    "Name the module, the transaction flow, the integration points, and a problem you resolved in it.",
    "Next 30 days", "Low", "Supported [process] in SAP [module] for [number] users, resolving [problem].",
)
SAP_CONFIG = _c(
    "sap_config", "SAP configuration and change",
    r"\b(?:configur\w*|customi[sz]\w*|abap|transports?|user\s+exits?|badi|fiori|odes?)\b", True,
    "Own one configuration change from request to transport",
    "Record the requirement, the configuration, the test evidence, and the transport.",
    "Next 30 days", "Medium", "Configured [change] in SAP [module], tested with [scenario] and transported to production.",
)
INTEGRATION = _c(
    "integration", "System integration",
    r"\b(?:idoc|bapi|rfc|odata|interfaces?|integrations?|middleware|pi/po|cpi|edi)\b", False,
    "Map one interface between SAP and another system",
    "Document the message flow, the failure handling, and the volume it carries.",
    "Next 90 days", "Medium", "Built the [interface] between SAP and [system], handling [volume] with [error handling].",
)
SALESFORCE_CORE = _c(
    "salesforce_core", "Salesforce platform",
    r"\b(?:salesforce|sfdc|apex|lightning|soql|crm)\b", True,
    "Build one feature in a Salesforce developer org",
    "Use objects, automation and a test class, and publish the setup steps.",
    "Next 30 days", "Medium", "Built [feature] in Salesforce using [objects/automation], covered by [number] Apex tests.",
)
CRM_AUTOMATION = _c(
    "crm_automation", "Automation and customisation",
    r"\b(?:flows?|process\s+builder|apex|triggers?|custom\s+objects?|validation\s+rules?|automation)\b", True,
    "Replace one manual CRM step with automation",
    "Measure how long the manual step took and what the automation does with bad data.",
    "Next 30 days", "Low", "Automated [process] in [CRM], removing [manual step] for [number] users.",
)
CRYPTO = _c(
    "crypto", "Cryptography in practice",
    r"\b(?:encrypt\w*|cryptograph\w*|tls|ssl|certificates?|pki|hashing|aes|rsa|keys?)\b", True,
    "Implement one cryptographic control correctly and explain the trade-off",
    "Key storage and rotation matter more than the algorithm. Write down what you chose and why.",
    "Next 30 days", "Medium", "Added [TLS/encryption] to [system], with keys stored in [where] and rotated [how often].",
)
THREAT_MODELLING = _c(
    "threat_modelling", "Threat modelling",
    r"\b(?:threat\s+model\w*|stride|attack\s+(?:surface|trees?)|risk\s+assess\w*|owasp)\b", True,
    "Threat-model one system you work on",
    "Draw the data flows, list the threats, and propose one mitigation you could actually build.",
    "Next 30 days", "Low", "Threat-modelled [system], identifying [number] issues and fixing [the top one].",
)
OFFENSIVE = _c(
    "offensive", "Offensive testing",
    r"\b(?:penetration\s+test\w*|pentest\w*|burp\s+suite|metasploit|nmap|exploit\w*|ctf|tryhackme|hack\s*the\s*box)\b", True,
    "Complete one lab end to end and write the report",
    "A TryHackMe or HackTheBox write-up shows method. Never include anything from a system you were not authorised to test.",
    "Next 30 days", "Medium", "Completed [lab/engagement], finding [number] vulnerabilities including [example], all with remediation advice.",
)
DEFENSIVE = _c(
    "defensive", "Detection and response",
    r"\b(?:siem|splunk|sentinel|detections?|alerts?|incident\s+response|forensics?|soc|playbooks?)\b", True,
    "Write one detection rule and test that it fires",
    "Pick an attack technique, build the alert, and run the technique in a lab to prove it triggers.",
    "Next 30 days", "Medium", "Wrote a [SIEM] detection for [technique], validated in a lab with [result].",
)
IAM = _c(
    "iam", "Identity and access",
    r"\b(?:iam|active\s+directory|sso|oauth|saml|oidc|mfa|privileged\s+access|rbac)\b", False,
    "Review access for one system and remove what is unused",
    "List who has access, who still needs it, and what you removed or tightened.",
    "Next 30 days", "Low", "Reviewed access to [system], removing [number] stale accounts and adding MFA for [group].",
)
COMPLIANCE = _c(
    "compliance", "Security standards and compliance",
    r"\b(?:iso\s*27001|soc\s*2|cyber\s+essentials|nist|gdpr|pci[\s-]?dss|policies|compliance)\b", False,
    "Map one control to evidence you already have",
    "Pick a control from Cyber Essentials or ISO 27001 and write down where the evidence lives. Only the control you actually checked belongs on a CV.",
    "Next 90 days", "Low", "Mapped [control] for [standard] to [evidence], closing [gap].",
)
CONTAINER = _c(
    "containers", "Containers and orchestration",
    r"\b(?:docker|kubernetes|k8s|helm|containeri[sz]\w*|pods?)\b", True,
    "Run a multi-container app locally and in a cluster",
    "Use Docker Compose, then deploy the same app to a small Kubernetes cluster.",
    "Next 30 days", "Medium", "Containerised [app] and deployed it to [Kubernetes] with [number] services.",
)
CICD = _c(
    "cicd", "CI/CD pipelines",
    r"\b(?:ci/cd|github\s+actions|gitlab\s+ci|jenkins|circleci|pipelines?|argo\s*cd)\b", True,
    "Build a pipeline that tests and deploys on every push",
    "Include a failing-test gate and a rollback step you have actually tried.",
    "This week", "Low", "Built a [GitHub Actions] pipeline that tests and deploys [app] on every push.",
)
IAC = _c(
    "iac", "Infrastructure as code",
    r"\b(?:terraform|cloudformation|ansible|pulumi|bicep|infrastructure\s+as\s+code)\b", True,
    "Rebuild your setup from code",
    "Destroy and recreate it to prove the code is complete.",
    "Next 30 days", "Medium", "Defined [environment] in Terraform, recreating it from scratch in [time].",
)
OBSERVABILITY = _c(
    "observability", "Monitoring and observability",
    r"\b(?:prometheus|grafana|datadog|monitoring|alerting|observability|logging|metrics|traces?|opentelemetry)\b", False,
    "Add monitoring and one alert to a running service",
    "Pick a meaningful signal such as error rate and test that the alert fires.",
    "Next 30 days", "Low", "Added [Prometheus/Grafana] monitoring and alerting for [service].",
)
ITSM = _c(
    "itsm", "IT service management",
    r"\b(?:itil|servicenow|incident\s+management|change\s+management|problem\s+management|cmdb|sla)\b", True,
    "Learn one ITSM process by running it",
    "Own incident, change or problem records for a month and note the volumes and outcomes.",
    "Next 30 days", "Low", "Managed [number] [incidents/changes] in [ServiceNow], meeting the [SLA] on [percentage].",
)
SYSADMIN = _c(
    "sysadmin", "Systems administration",
    r"\b(?:windows\s+server|active\s+directory|group\s+policy|linux|servers?|patch(?:ing|ed)?|backups?)\b", True,
    "Own one server or service end to end",
    "Patching, backups you have restored, and monitoring. A restore you have tested counts double.",
    "Next 30 days", "Medium", "Administered [system] for [number] users, including tested backups and patching.",
)
ENDPOINTS = _c(
    "endpoints", "End-user devices and support",
    r"\b(?:intune|jamf|sccm|mecm|mdm|imaging|laptops?|desktops?|mobile\s+devices?|office\s*365|microsoft\s+365)\b", True,
    "Automate one device task",
    "Build-from-image, zero-touch enrolment or an Intune policy. Record the time it saves.",
    "Next 30 days", "Medium", "Automated [device task] with [Intune], cutting setup from [before] to [after].",
)
TICKETING = _c(
    "ticketing", "Ticket handling",
    r"\b(?:tickets?|service\s+desk|help\s*desk|queues?|first[\s-]line|second[\s-]line)\b", True,
    "Track your own ticket numbers for a month",
    "Volume, first-contact resolution and average time are the figures that turn a duty into evidence.",
    "This week", "Low", "Resolved around [number] tickets a week, [percentage] at first contact.",
)
CUSTOMER_COMMS = _c(
    "customer_comms", "Explaining technical problems to non-technical people",
    r"\b(?:customers?|users?|callers?|explained|explaining|non[\s-]technical|stakeholders?)\b", True,
    "Rewrite one technical fix as an explanation a user understood",
    "Keep both versions. The ability to translate is half of a support role.",
    "This week", "Low", "Explained [problem] to [user] and confirmed they could [do the task] afterwards.",
)
VENDOR_MGMT = _c(
    "vendors", "Vendors and procurement",
    r"\b(?:vendors?|suppliers?|procurement|licen[cs]es?|contracts?|renewals?)\b", False,
    "Own one licence renewal or vendor issue",
    "Note the cost, the users affected, and the outcome.",
    "Next 90 days", "Low", "Managed the [product] renewal for [number] users, [saving/outcome].",
)
ARCHITECTURE = _c(
    "architecture", "System design and architecture",
    r"\b(?:architect\w*|system\s+design|trade[\s-]?offs?|scalability|design\s+docs?|rfcs?|adrs?)\b", True,
    "Write one design document with the options you rejected",
    "The rejected options and why are what separate architecture from implementation.",
    "Next 30 days", "Medium", "Wrote the design for [system], choosing [option] over [alternative] because [reason].",
)
LEADERSHIP = _c(
    "leadership", "Technical leadership",
    r"\b(?:led|leading|mentored|mentoring|coached|hiring|code\s+reviews?|standards?|guild|chapter)\b", True,
    "Mentor one person and write down what changed for them",
    "Their output, not your advice, is the evidence.",
    "Next 90 days", "Medium", "Mentored [person/number] on [area]; they went on to [deliver what].",
)
ROADMAP = _c(
    "roadmap", "Roadmaps and prioritisation",
    r"\b(?:roadmaps?|prioriti[sz]\w*|backlogs?|discovery|opportunities|bets?)\b", True,
    "Write a one-page roadmap and the evidence behind the top item",
    "Show what you said no to. Prioritisation is the job.",
    "Next 30 days", "Low", "Prioritised [area] into a roadmap, putting [item] first because [evidence].",
)
DISCOVERY = _c(
    "discovery", "Discovery and requirements",
    r"\b(?:discovery|user\s+(?:research|interviews?)|requirements|problem\s+framing|opportunit\w*)\b", True,
    "Run discovery before one piece of build",
    "Talk to the people with the problem, write the requirement, and record what you cut from scope.",
    "Next 30 days", "Low", "Ran discovery for [problem] with [number] users, scoping [feature] down to [outcome].",
)
EXPERIMENTATION = _c(
    "experimentation", "Experiments",
    r"\b(?:experiments?|a/b\s+tests?|hypothes\w*|rollouts?|feature\s+flags?)\b", False,
    "Ship one change behind a flag and measure it",
    "Write the hypothesis first, then the result, including a result you did not expect.",
    "Next 30 days", "Medium", "Tested [change] against [baseline], moving [metric] from [before] to [after].",
)
ACCESSIBILITY = _c(
    "accessibility", "Accessibility",
    r"\b(?:accessib\w*|wcag|aria|screen\s+readers?|keyboard\s+navigation|inclusive\s+design)\b", False,
    "Audit one flow and fix what you find",
    "Keyboard-only use plus a screen reader will find the important issues. Record the before and after.",
    "This week", "Low", "Fixed [number] accessibility issues in [flow], retested with [screen reader].",
)
DESIGN_TOOLS = _c(
    "design_tools", "Design tools",
    r"\b(?:figma|sketch|adobe\s+xd|prototyp\w*|design\s+systems?)\b", True,
    "Design one flow in Figma and hand it to someone else to build",
    "The handoff is the test: components, states, and annotations they did not need to ask about.",
    "Next 30 days", "Low", "Designed [flow] in Figma; [developer] built it with [number] clarification questions.",
)
RESEARCH_METHOD = _c(
    "research_method", "User research",
    r"\b(?:user\s+(?:research|interviews?|testing)|usability\s+(?:tests?|studies)|surveys?|participants?)\b", True,
    "Run five usability sessions on one flow",
    "Write a short script, record what people do rather than what they say, and report the pattern.",
    "Next 30 days", "Medium", "Ran [number] usability sessions on [flow], finding [pattern] and changing [thing].",
)
CONTENT_DESIGN = _c(
    "content_design", "Content and interface writing",
    r"\b(?:microcopy|ux\s+writing|content\s+design|error\s+messages?|labels?|copy)\b", False,
    "Rewrite the error and empty states for one flow",
    "These decide whether users recover. Test the new wording with someone unfamiliar with the product.",
    "This week", "Low", "Rewrote [number] error states in [flow], reducing [support contacts/drop-off].",
)
BUSINESS_SYSTEMS = _c(
    "business_systems", "Business systems and processes",
    r"\b(?:erp|crm|workflow|process(?:es)?|requirements?|stakeholders?|systems?)\b", True,
    "Own one business process end to end",
    "Map it, find the slowest or most error-prone step, and change the system to fix it.",
    "Next 30 days", "Medium", "Mapped [process] across [systems] and removed [step], saving [time] per [cycle].",
)
SQL_ANALYSIS = _c(
    "sql_analysis", "SQL and reporting",
    r"\b(?:sql|queries|reports?|dashboards?|excel|power\s*bi)\b", True,
    "Replace one manual report with a query or dashboard",
    "Note who uses it and how long the manual version took.",
    "This week", "Low", "Replaced the manual [report] with a [SQL] query, cutting preparation from [before] to [after].",
)
POWER_PLATFORM = _c(
    "power_platform", "Low-code automation",
    r"\b(?:power\s+(?:automate|apps|bi)|sharepoint|logic\s+apps|low[\s-]code)\b", False,
    "Automate one approval or data-entry step",
    "Low-code counts when it removes real work. Record whose work and how much.",
    "Next 30 days", "Low", "Automated [process] with [Power Automate], removing [manual step] for [team].",
)
TELEPHONY = _c(
    "telephony", "Telephony and collaboration platforms",
    r"\b(?:teams|zoom|telephony|sip|voip|pbx|call\s+queues?|contact\s+cent(?:er|re))\b", False,
    "Own one telephony or collaboration change",
    "A migration, a call queue or a rooms setup. Record the users affected and the problems you caught.",
    "Next 30 days", "Low", "Migrated [number] users to [platform], resolving [problem] during cutover.",
)
M365 = _c(
    "m365", "Microsoft 365 administration",
    r"\b(?:microsoft\s+365|office\s*365|exchange|sharepoint|entra|azure\s+ad|tenant)\b", True,
    "Administer one tenant task you can show",
    "A conditional access policy, a migration, or a retention rule. Record the users it covers.",
    "Next 30 days", "Low", "Configured [policy] in [Microsoft 365] covering [number] users, [outcome].",
)
