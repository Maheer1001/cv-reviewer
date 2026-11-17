"""The IT vocabulary the deterministic checks use.

Every pattern here decides whether a line "names a method" and whether a listed skill is real. Patterns are
deliberately specific: generic words like "support", "users" or "network" would promote duty-only bullets, so
they are not skills. Short or ambiguous tokens (Go, R, C, SAP, ARM) are guarded so ordinary English does not
match them.
"""

import re
from typing import Dict, Tuple

_I = re.I


def _rx(expr: str, flags: int = _I) -> re.Pattern:
    return re.compile(expr, flags)


# name -> (category, pattern). Categories are display groups only; scoring treats every entry the same.
CANONICAL_SKILLS: Dict[str, Tuple[str, re.Pattern]] = {
    # Languages
    "Python": ("Languages", _rx(r"\bpython\b")),
    "JavaScript": ("Languages", _rx(r"\bjavascript\b|\bjs\b")),
    "TypeScript": ("Languages", _rx(r"\btypescript\b|\bts\b")),
    "Java": ("Languages", _rx(r"\bjava\b(?!\s*script)")),
    "C++": ("Languages", _rx(r"\bc\+\+")),
    "C#": ("Languages", _rx(r"\bc#")),
    # "C" alone is only counted when listed, or next to another language, so "C grade" never matches.
    "C": ("Languages", _rx(r"(?:^|[,|/•;:]\s*)C(?=\s*(?:[,|/•;]|$))|\bC\s*(?:/|&|and)\s*(?:C\+\+|C#|python|java)\b", re.M)),
    "Go": ("Languages", _rx(r"\bgolang\b|\bgo\b(?=\s+(?:microservice|routines|api|backend|service))")),
    "Rust": ("Languages", _rx(r"\brust\b")),
    "Kotlin": ("Languages", _rx(r"\bkotlin\b")),
    "Swift": ("Languages", _rx(r"\bswift\b|\bswiftui\b")),
    "PHP": ("Languages", _rx(r"\bphp\b")),
    "Ruby": ("Languages", _rx(r"\bruby\b")),
    "Scala": ("Languages", _rx(r"\bscala\b")),
    "Dart": ("Languages", _rx(r"\bdart\b")),
    "SQL": ("Languages", _rx(r"\bsql\b|\bt[\s-]?sql\b")),
    "Bash / Shell": ("Languages", _rx(r"\bbash\b|\bshell\s+script\w*|\bpowershell\b|\bzsh\b")),
    # "R" is case-sensitive and only counted in a list or after "in/using/with/and", so initials and R&D don't match.
    "R": ("Languages", _rx(r"\b(?:in|using|with|and)\s+R\b(?!&)|(?:^|[,|/•;:]\s*)R(?=\s*(?:[,|/•;]|$))|\bR\s?Studio\b|\b(?:tidyverse|ggplot2?|dplyr)\b", re.M)),
    "MATLAB": ("Languages", _rx(r"\bmatlab\b")),
    "VHDL / Verilog": ("Languages", _rx(r"\bvhdl\b|\bverilog\b|\bsystemverilog\b")),
    "Assembly": ("Languages", _rx(r"\bassembly\b|\basm\b")),
    # Frontend
    "HTML/CSS": ("Frontend", _rx(r"\bhtml5?\b|\bcss3?\b|\bsass\b|\bscss\b|\btailwind\b")),
    "React": ("Frontend", _rx(r"\breact(?:\.js|js| native)?\b")),
    "Next.js": ("Frontend", _rx(r"\bnext(?:\.js|js)\b")),
    "Vue.js": ("Frontend", _rx(r"\bvue(?:\.js|js)?\b|\bnuxt\b")),
    "Angular": ("Frontend", _rx(r"\bangular\b")),
    "Svelte": ("Frontend", _rx(r"\bsvelte(?:kit)?\b")),
    # Backend and APIs
    "Node.js": ("Backend & APIs", _rx(r"\bnode(?:\.js|js)?\b")),
    "FastAPI": ("Backend & APIs", _rx(r"\bfastapi\b")),
    "Django": ("Backend & APIs", _rx(r"\bdjango\b")),
    "Flask": ("Backend & APIs", _rx(r"\bflask\b")),
    "Spring Boot": ("Backend & APIs", _rx(r"\bspring(?:\s+boot)?\b")),
    "Laravel": ("Backend & APIs", _rx(r"\blaravel\b")),
    "Ruby on Rails": ("Backend & APIs", _rx(r"\brails\b")),
    ".NET": ("Backend & APIs", _rx(r"\b\.net\b|\basp\.net\b|\bdotnet\b")),
    "Express": ("Backend & APIs", _rx(r"\bexpress(?:\.js|js)?\b")),
    "GraphQL": ("Backend & APIs", _rx(r"\bgraphql\b")),
    "REST APIs": ("Backend & APIs", _rx(r"\brest(?:ful)?\s+apis?\b")),
    "gRPC": ("Backend & APIs", _rx(r"\bgrpc\b")),
    # Data and storage
    "PostgreSQL": ("Data & Storage", _rx(r"\bpostgres(?:ql)?\b")),
    "MySQL": ("Data & Storage", _rx(r"\bmysql\b|\bmariadb\b")),
    "SQL Server": ("Data & Storage", _rx(r"\bsql\s+server\b|\bmssql\b")),
    "MongoDB": ("Data & Storage", _rx(r"\bmongodb\b|\bmongo\b")),
    "Redis": ("Data & Storage", _rx(r"\bredis\b")),
    "Elasticsearch": ("Data & Storage", _rx(r"\belasticsearch\b|\bopensearch\b")),
    "Kafka": ("Data & Storage", _rx(r"\bkafka\b")),
    "Snowflake": ("Data & Storage", _rx(r"\bsnowflake\b")),
    "BigQuery": ("Data & Storage", _rx(r"\bbigquery\b")),
    "dbt": ("Data & Storage", _rx(r"\bdbt\b")),
    # Data and machine learning
    "Pandas": ("Data & ML", _rx(r"\bpandas\b")),
    "NumPy": ("Data & ML", _rx(r"\bnumpy\b")),
    "PyTorch": ("Data & ML", _rx(r"\bpytorch\b")),
    "TensorFlow": ("Data & ML", _rx(r"\btensorflow\b|\bkeras\b")),
    "Scikit-learn": ("Data & ML", _rx(r"\bscikit[\s-]?learn\b|\bsklearn\b")),
    "Spark": ("Data & ML", _rx(r"\b(?:apache\s+)?spark\b|\bpyspark\b")),
    "Airflow": ("Data & ML", _rx(r"\bairflow\b")),
    "Hugging Face": ("Data & ML", _rx(r"\bhugging\s*face\b|\btransformers\b")),
    "Power BI": ("Data & ML", _rx(r"\bpower\s*bi\b")),
    "Tableau": ("Data & ML", _rx(r"\btableau\b")),
    "Excel": ("Data & ML", _rx(r"\bexcel\b|\bspreadsheets?\b|\bpivot\s+tables?\b")),
    # Cloud and DevOps
    "Docker": ("Cloud & DevOps", _rx(r"\bdocker\b")),
    "Kubernetes": ("Cloud & DevOps", _rx(r"\bkubernetes\b|\bk8s\b")),
    "AWS": ("Cloud & DevOps", _rx(r"\baws\b|\bamazon\s+web\s+services\b|\bec2\b|\bs3\b|\brds\b|\beks\b")),
    "Azure": ("Cloud & DevOps", _rx(r"\bazure\b")),
    "GCP": ("Cloud & DevOps", _rx(r"\bgcp\b|\bgoogle\s+cloud\b")),
    "Terraform": ("Cloud & DevOps", _rx(r"\bterraform\b")),
    "Ansible": ("Cloud & DevOps", _rx(r"\bansible\b")),
    "CI/CD": ("Cloud & DevOps", _rx(r"\bci/cd\b|\bgithub\s+actions\b|\bgitlab\s+ci\b|\bjenkins\b|\bcircleci\b")),
    "Linux": ("Cloud & DevOps", _rx(r"\blinux\b|\bubuntu\b|\bdebian\b|\bcentos\b|\brhel\b")),
    "Prometheus / Grafana": ("Cloud & DevOps", _rx(r"\bprometheus\b|\bgrafana\b|\bdatadog\b")),
    # Security
    "Burp Suite": ("Security", _rx(r"\bburp\s+suite\b")),
    "Metasploit": ("Security", _rx(r"\bmetasploit\b")),
    "Wireshark": ("Security", _rx(r"\bwireshark\b")),
    "Nmap": ("Security", _rx(r"\bnmap\b")),
    "SIEM": ("Security", _rx(r"\bsiem\b|\bsplunk\b|\bsentinel\b")),
    "OWASP": ("Security", _rx(r"\bowasp\b")),
    # Networking
    "Cisco": ("Networking", _rx(r"\bcisco\b|\bccna\b|\bccnp\b")),
    "TCP/IP": ("Networking", _rx(r"\btcp/ip\b|\bosi\s+model\b")),
    "BGP / OSPF": ("Networking", _rx(r"\bbgp\b|\bospf\b|\beigrp\b|\bmp(?:ls|bgp)\b")),
    "DNS / DHCP": ("Networking", _rx(r"\bdns\b|\bdhcp\b")),
    "Firewalls": ("Networking", _rx(r"\bfirewalls?\b|\bpalo\s+alto\b|\bfortigate\b|\bpfSense\b")),
    "VLANs": ("Networking", _rx(r"\bvlans?\b")),
    # Embedded, robotics and hardware
    "Arduino": ("Embedded & Robotics", _rx(r"\barduino\b")),
    "Raspberry Pi": ("Embedded & Robotics", _rx(r"\braspberry\s+pi\b")),
    "ROS": ("Embedded & Robotics", _rx(r"\bros\s*2?\b|\brobot\s+operating\s+system\b")),
    "Embedded C": ("Embedded & Robotics", _rx(r"\bembedded\s+(?:c|c\+\+|systems?|software|linux)\b|\bfirmware\b")),
    "STM32 / ESP32": ("Embedded & Robotics", _rx(r"\bstm32\b|\besp32\b|\besp8266\b")),
    "PCB Design": ("Embedded & Robotics", _rx(r"\bpcbs?\b|\bkicad\b|\beagle\b|\baltium\b|\bcircuit\s+(?:design|boards?)\b")),
    "FPGAs": ("Embedded & Robotics", _rx(r"\bfpgas?\b")),
    "Microcontrollers": ("Embedded & Robotics", _rx(r"\bmicrocontrollers?\b|\bmcus?\b")),
    "RTOS": ("Embedded & Robotics", _rx(r"\brtos\b|\bfreertos\b")),
    "Sensors": ("Embedded & Robotics", _rx(r"\b(?:lidar|imu|encoders?|ultrasonic|gyroscopes?|accelerometers?)\b|\bsensors?\b")),
    "Control Systems": ("Embedded & Robotics", _rx(r"\bpid\s+control\w*|\bcontrol\s+(?:loops?|systems?|theory)\b|\bkalman\s+filters?\b")),
    "Computer Vision": ("Embedded & Robotics", _rx(r"\bcomputer\s+vision\b|\bopencv\b|\bobject\s+detection\b")),
    "PLCs": ("Embedded & Robotics", _rx(r"\bplcs?\b|\bscada\b|\bladder\s+logic\b")),
    "CAD": ("Embedded & Robotics", _rx(r"\bcad\b|\bsolidworks\b|\bfusion\s*360\b|\bautodesk\s+inventor\b|\bonshape\b")),
    "3D Printing": ("Embedded & Robotics", _rx(r"\b3d\s+print\w*")),
    # Mobile and games
    "Flutter": ("Mobile & Games", _rx(r"\bflutter\b")),
    "React Native": ("Mobile & Games", _rx(r"\breact\s+native\b")),
    "Android": ("Mobile & Games", _rx(r"\bandroid\b|\bjetpack\s+compose\b")),
    "iOS": ("Mobile & Games", _rx(r"\bios\b|\bswiftui\b|\buikit\b|\bxcode\b")),
    "Unity": ("Mobile & Games", _rx(r"\bunity\b")),
    "Unreal Engine": ("Mobile & Games", _rx(r"\bunreal(?:\s+engine)?\b")),
    "Godot": ("Mobile & Games", _rx(r"\bgodot\b")),
    # QA and UX
    "Selenium": ("QA & UX", _rx(r"\bselenium\b")),
    "Cypress": ("QA & UX", _rx(r"\bcypress\b")),
    "Playwright": ("QA & UX", _rx(r"\bplaywright\b")),
    "Appium": ("QA & UX", _rx(r"\bappium\b")),
    "JMeter": ("QA & UX", _rx(r"\bjmeter\b|\bk6\b|\bgatling\b|\blocust\b")),
    "Figma": ("QA & UX", _rx(r"\bfigma\b|\bsketch\b|\badobe\s+xd\b")),
    "Accessibility": ("QA & UX", _rx(r"\baccessib\w*|\bwcag\b|\baria\b")),
    # Business systems
    "SAP": ("ERP & CRM", _rx(r"\bsap\b|\bs/4hana\b|\babap\b|\bidocs?\b|\bbapis?\b")),
    "Salesforce": ("ERP & CRM", _rx(r"\bsalesforce\b|\bapex\b|\bsoql\b")),
    "Dynamics 365": ("ERP & CRM", _rx(r"\bdynamics\s+365\b")),
    "ServiceNow": ("ERP & CRM", _rx(r"\bservicenow\b")),
    "Power Automate": ("ERP & CRM", _rx(r"\bpower\s+automate\b|\bpower\s+apps\b")),
    # Practices and ways of working
    "Git": ("Practices", _rx(r"\bgit\b|\bgithub\b|\bgitlab\b")),
    "Pytest / Unit Testing": ("Practices", _rx(r"\bpytest\b|\bjest\b|\bjunit\b|\bnunit\b|\bunit\s+test(?:s|ing)?\b|\btdd\b|\bintegration\s+test(?:s|ing)?\b")),
    "Agile / Scrum": ("Practices", _rx(r"\bagile\b|\bscrum\b|\bkanban\b")),
    "Jira": ("Practices", _rx(r"\bjira\b|\bconfluence\b")),
    "LaTeX": ("Practices", _rx(r"\blatex\b|\boverleaf\b")),
}

# Software techniques. "using/via/by doing" covers methods this list doesn't name.
SOFTWARE_METHOD_REGEX = _rx(
    r"\b(?:using|via|through|by\s+implementing|by\s+building|by\s+refactoring|by\s+redesigning|by\s+automating|"
    r"microservice|architecture|pipeline|index(?:e[ds]|ing)?|caching|cache|batch(?:ing)?|asynchronous|async|"
    r"concurrency|thread|algorithm|schema|migration|ci/cd|unit\s+test|integration\s+tests?|regression|"
    r"authentication|oauth|jwt|encryption|load\s+balanc|sharding|partitioning|profil(?:e|ed|ing)|benchmark|"
    r"query|subquery|idempoten\w*|retries|retry|callback|latency|p95|p99|endpoint|database|"
    r"workflow|constraint|replay|suite|join)\b"
)

# Named techniques in the wider IT field. Kept specific so duty-only bullets ("helped users", "managed the
# network") are not promoted.
IT_METHOD_TERMS: Dict[str, str] = {
    "data_ai": (
        r"models?|classif\w*|regression|cluster(?:ing|ed)?|neural\s+net\w*|transformers?|fine[\s-]?tun\w*|embeddings?|"
        r"feature\s+(?:engineering|stores?)|etl|elt|data\s+warehous\w*|data\s+lakes?|star\s+schemas?|dimensional\s+model\w*|"
        r"dashboards?|notebooks?|cross[\s-]?validat\w*|hyperparameters?|baselines?|precision|recall|f1[\s-]?scores?|"
        r"confusion\s+matri\w*|overfitting|tokeni[sz]\w*|rag\b|retrieval[\s-]augmented|vector\s+(?:databases?|stores?)|"
        r"prompt\s+engineering|llms?|large\s+language\s+models?|a/b\s+tests?"
    ),
    "security": (
        r"penetration\s+tests?|pentests?|vulnerabilit(?:y|ies)\s+(?:scans?|assessments?|management)|threat\s+model\w*|"
        r"static\s+analysis|sast|dast|code\s+reviews?|incident\s+response|forensics?|malware\s+analys\w*|"
        r"packet\s+captures?|intrusion\s+detection|ids|ips|zero[\s-]trust|least\s+privilege|mfa|multi[\s-]factor|"
        r"phishing\s+simulations?|security\s+audits?|hardening|patch\s+management|cves?|cvss|"
        r"sql\s+injection|xss|cross[\s-]site\s+scripting|owasp|siem|soc\s+alerts?|"
        r"idor|ssrf|csrf|rce|lfi|privesc|privilege\s+escalation|retests?|write[\s-]?ups?|"
        r"tryhackme|hack\s*the\s*box|htb|offsec|portswigger|thm|ctf|proving\s+grounds|"
        r"footholds?|domain\s+admin|root\s+shells?|reverse\s+shells?|attack\s+paths?|"
        r"phishing|contained|containment|compromis\w*|true\s+positives?|false\s+positives?"
    ),
    "networking": (
        r"tcp/ip|subnets?|subnetting|cidrs?|vlans?|vpns?|routing\s+(?:tables?|protocols?)|bgp|ospf|eigrp|"
        r"dns\s+(?:records?|resolution|servers?)|dhcp|firewalls?|load\s+balancers?|packet\s+(?:captures?|analysis)|"
        r"latency|throughput|bandwidth|qos|mpls|sd[\s-]wan|wireshark|network\s+diagrams?"
    ),
    "support": (
        r"ticketing\s+systems?|service\s+desk|active\s+directory|group\s+polic\w*|intune|mdm|jamf|"
        r"remote\s+(?:support|desktop)|imaging|sla|slas|root[\s-]cause|knowledge\s+base|runbooks?|"
        r"onboarding\s+(?:new\s+)?(?:starters|joiners|users|staff)|escalat\w*"
    ),
    "embedded_robotics": (
        r"firmware|microcontrollers?|interrupts?|registers?|gpio|i2c|spi|uart|can\s+bus|pwm|adc|dac|"
        r"rtos|real[\s-]time|schematics?|pcbs?|soldering|oscilloscopes?|logic\s+analy[sz]ers?|"
        r"debuggers?|jtag|swd|bootloaders?|device\s+drivers?|kernel\s+modules?|"
        r"pid\s+control\w*|control\s+loops?|kalman\s+filters?|state\s+machines?|odometry|kinematics|"
        r"inverse\s+kinematics|slam|path\s+plann\w*|computer\s+vision|sensor\s+fusion|"
        r"lidar|imu|encoders?|motor\s+(?:control|drivers?)|servos?|actuators?|ros\s*2?|"
        r"cad|3d\s+print\w*|prototyp\w*|test\s+(?:rigs?|benches|fixtures)|fpgas?|vhdl|verilog|"
        r"plc|scada|ladder\s+logic|hmi"
    ),
    "mobile_games": (
        r"mobile\s+apps?|app\s+stores?|push\s+notifications?|offline[\s-]first|responsive\s+layouts?|"
        r"game\s+loops?|physics\s+engines?|shaders?|rendering|frame\s+rates?|gameplay|level\s+design|"
        r"multiplayer|netcode|collision\s+detection"
    ),
    "qa_ux": (
        r"test\s+(?:plans?|cases|suites?|strategies|automation|coverage)|regression\s+tests?|exploratory\s+testing|"
        r"boundary\s+(?:tests?|cases)|edge\s+cases|bug\s+(?:reports?|triage)|severity|reproduc\w*|"
        r"usability\s+(?:tests?|testing|studies|sessions?)|user\s+(?:research|interviews?|testing|journeys)|wireframes?|"
        r"prototypes?|design\s+systems?|personas?|a/b\s+tests?|heuristics?|wcag|screen\s+readers?"
    ),
    "product_delivery": (
        r"roadmaps?|backlogs?|user\s+stor(?:y|ies)|acceptance\s+criteria|sprint\s+(?:planning|reviews?|retrospectives?)|"
        r"kpis?|okrs?|product\s+metrics|funnels?|conversion\s+rates?|retention|churn|"
        r"stakeholder\s+(?:workshops?|interviews?)|requirements|specifications?|"
        r"discovery|regressions?|go[\s-]live|rollouts?|feature\s+flags?|"
        r"release\s+strateg\w*|transport\s+requests?|goods\s+receipts?|purchase\s+orders?"
    ),
}
IT_METHOD_REGEX = _rx(r"\b(?:" + "|".join(IT_METHOD_TERMS.values()) + r")\b")

# "by automating the checks" is a method; "by being helpful" is not.
GENERIC_MECHANISM_REGEX = _rx(
    r"\bby\s+(?!(?:being|working|helping|doing|trying|going|getting|making\s+sure|ensuring)\b)[a-z]+ing\b"
)

_NUMBER = (
    r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?|"
    r"(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|hundreds?|thousands?|dozens?)\b)"
)
_SCOPE_UNITS = (
    r"%|ms|s|seconds|minutes|hours|days|weeks|months|x|gb|tb|mb|kb|req/s|rps|tps|fps|ghz|mhz|"
    r"users|clients|customers|endpoints|services|tables|pipelines|records|rows|transactions|commits|tests|bookings|"
    r"events|requests|deployments|releases|builds|incidents|alerts|tickets|vulnerabilities|findings|cves|"
    r"devices|servers|nodes|clusters|containers|machines|sites|offices|stores|branches|"
    r"students|pupils|people|staff|colleagues|engineers|developers|"
    r"sensors|robots|motors|joints|axes|channels|pins|gates|lines\s+of\s+code|"
    r"screens|pages|components|features|stories|sprints|repositories|modules|microservices|"
    r"models|datasets|samples|features|images|frames|packets|flows|queries|dashboards|reports|measures|"
    r"players|levels|assets|scenarios|test\s+cases|defects|bugs|regressions|vulnerabilities|findings|"
    r"alerts|false\s+positives|accounts|permissions|rules|records|sessions|questions|"
    r"endpoints|services|pipelines|jobs|tables|views|checks|controls|risks|gaps"
)
_HYPHEN_SCOPE = (
    r"person|people|strong|node|service|site|server|week|month|day|hour|page|module|sprint|player|user|device|robot"
)
METRIC_OR_SCOPE_REGEX = _rx(
    r"(?:\b" + _NUMBER + r"\s*[km]?\b(?:\s+[\w'-]+){0,3}\s*(?:" + _SCOPE_UNITS + r")\b|"
    r"\b\d+(?:\.\d+)?\s*%|"
    r"(?:£|\$|€)\s*\d+(?:[.,]\d+)?\s*(?:k|m|bn|b)?|"
    r"\b\d+(?:,\d{3})*-(?:" + _HYPHEN_SCOPE + r")\b|"
    r"\bfrom\s+" + _NUMBER + r"[^\n]{1,40}?\bto\s+(?:" + _NUMBER + r"|half\b)|"
    r"\b(?:cut(?:ting)?|reduc(?:e|ed|ing)|lower(?:ed|ing)?|rais(?:e|ed|ing)|improv(?:e|ed|ing)|increas(?:e|ed|ing)|"
    r"sav(?:e|ed|ing)|dropp(?:ed|ing)|brought|moves?|mov(?:ed|ing))\b[^\n]{0,50}?\bfrom\s+\w+[^\n]{0,40}?\bto\s+\w+)"
)
BASELINE_REGEX = _rx(r"\bfrom\s+" + _NUMBER + r"[^\n]{1,40}?\bto\s+(?:" + _NUMBER + r"|half\b)")

OUTCOME_SIGNAL_REGEX = _rx(
    r"\b(?:reducing|reduced|increasing|increased|cutting|cut|eliminating|eliminated|saving|saved|"
    r"accelerating|accelerated|lowering|lowered|preventing|prevented|enabling|enabled|resulting\s+in|"
    r"achieving|achieved|delivering|delivered|halving|halved|doubling|doubled|improving|improved|raising|raised|grew|growing|"
    r"won|winning|secured|securing|recovered|recovering|resolved|resolving|passed|approved|adopted|accepted|published|"
    r"shipped|shipping|launched|launching|deployed|deploying|migrated|migrating|automated|automating|"
    r"detected|detecting|identified|identifying|fixed|fixing|caught|catching|blocked|blocking|"
    r"reproduced|reproducing|trained|training|fine[\s-]?tuned|ranked|reaching|reached|"
    r"built|building|designed|designing|wrote|written|writing|implemented|implementing|"
    r"created|creating|developed|developing|added|adding|introduced|introducing|"
    r"configured|configuring|integrated|integrating|modelled|modeling|modeled|"
    r"replaced|replacing|removed|removing|moved|moving|refactored|refactoring|"
    r"reviewed|reviewing|tested|testing|verified|verifying|validated|validating|"
    r"diagnosed|diagnosing|traced|tracing|tuned|tuning|optimised|optimized|"
    r"monitored|monitoring|restored|restoring|patched|patching|hardened|hardening|"
    r"documented|documenting|specified|specifying|defined|defining|scoped|scoping|"
    r"triaged|triaging|resolved|resolving|answered|answering|onboarded|onboarding|"
    r"mentored|mentoring|coached|coaching|led|leading|owned|owning|"
    r"presented|presenting|ran|running|completed|completing|achieved|achieving)\b"
)
