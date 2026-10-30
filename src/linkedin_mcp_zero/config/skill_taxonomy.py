"""Structured skill taxonomy: canonical names, aliases, categories and seed relations.

Line format inside each category block:  Canonical | alias, alias | related, related
Relations are mirrored (A<->B) when seeded into the skill graph, so a fresh install
already has useful ``expand_skill_cluster`` answers (no cold start).
"""

from __future__ import annotations

_RAW: dict[str, str] = {
    "language": """
Python | py | Django, Flask, FastAPI, Pandas
JavaScript | js, ecmascript | TypeScript, React, Node.js
TypeScript | ts | JavaScript, React, Node.js
Go | golang | Docker, Kubernetes
Rust | | Go
Java | | Spring Boot, SQL
C++ | cpp | C
C# | csharp, c-sharp | .NET
C | | C++
Ruby | | Ruby on Rails
PHP | | MySQL
Swift | | Kotlin
Kotlin | | Java, Android
Scala | | Spark
R | | Statistics, Data Analytics
Dart | | Flutter
SQL | | PostgreSQL, MySQL, Data Analytics
Bash | shell scripting, shell script | Linux
HTML | html5 | CSS, JavaScript
CSS | css3 | HTML, Tailwind
""",
    "frontend": """
React | react.js, reactjs | Redux, Next.js, TypeScript
React Native | | React, Flutter
Vue | vue.js, vuejs | Nuxt
Angular | angularjs | TypeScript
Svelte | | JavaScript
Next.js | nextjs | React
Nuxt | nuxt.js | Vue
Tailwind | tailwindcss, tailwind css | CSS
Redux | | React
Vite | | JavaScript
Webpack | | JavaScript
GraphQL | | REST, Node.js
REST | rest api, restful, rest apis | GraphQL, FastAPI
WebSockets | websocket | Node.js
""",
    "backend": """
Node.js | node, nodejs | Express, NestJS, JavaScript
Express | express.js, expressjs | Node.js
FastAPI | | Python, REST
Django | | Python, PostgreSQL
Flask | | Python
Spring Boot | springboot | Java, Spring
Spring | | Java
ASP.NET | asp.net core | C#, .NET
.NET | dotnet, .net core | C#
Ruby on Rails | rails, ror | Ruby
NestJS | nest.js | Node.js, TypeScript
gRPC | | REST
""",
    "cloud": """
AWS | amazon web services | Lambda, Terraform, Docker
Azure | microsoft azure | Terraform
GCP | google cloud, google cloud platform | Kubernetes
Terraform | | AWS, Ansible
Ansible | | Linux, Terraform
Serverless | | AWS, Lambda
Lambda | aws lambda | AWS
""",
    "devops": """
Docker | containers, containerization | Kubernetes, Linux
Kubernetes | k8s | Docker, Helm
Helm | | Kubernetes
Jenkins | | CI/CD
CI/CD | cicd, ci cd | GitHub Actions, Jenkins
GitHub Actions | | CI/CD
GitLab CI | gitlab ci/cd | CI/CD
Prometheus | | Grafana
Grafana | | Prometheus
Datadog | | Prometheus
Git | github, gitlab | CI/CD
""",
    "database": """
PostgreSQL | postgres, psql | SQL
MySQL | mariadb | SQL
SQLite | | SQL
MongoDB | mongo | Node.js
Redis | | Python
Elasticsearch | elastic search, opensearch | Kafka
DynamoDB | | AWS
Snowflake | | SQL, dbt
BigQuery | | GCP, SQL
ClickHouse | | SQL
Qdrant | | RAG
Pinecone | | RAG
Chroma | chromadb | RAG
""",
    "messaging": """
Apache Kafka | kafka | Spark
RabbitMQ | | Celery
Celery | | Python, Redis
""",
    "ai": """
Machine Learning | ml | Deep Learning, Python, scikit-learn
Deep Learning | | PyTorch, TensorFlow
AI | artificial intelligence | Machine Learning, LLM
LLM | llms, large language models, large language model | RAG, Prompt Engineering, LangChain
Generative AI | genai, gen ai | LLM
Prompt Engineering | | LLM
RAG | retrieval augmented generation, retrieval-augmented generation | LLM, Vector Databases
Vector Databases | vector database, vector db | RAG
NLP | natural language processing | LLM
Computer Vision | cv | PyTorch
PyTorch | torch | Deep Learning
TensorFlow | | Keras
Keras | | TensorFlow
scikit-learn | sklearn | Pandas
Pandas | | NumPy, Python
NumPy | | Pandas
Polars | | Pandas
Spark | apache spark | PySpark, Scala
PySpark | | Spark
Airflow | apache airflow | Python
dbt | | SQL, Snowflake
Hugging Face | huggingface | LLM
LangChain | | LLM, RAG
LlamaIndex | | RAG
OpenAI API | openai, gpt | LLM
Claude API | anthropic | LLM
MCP | model context protocol | LLM
AI Agents | agentic ai, ai agent | LLM, MCP
""",
    "automation": """
n8n | | Zapier, Make
Zapier | | n8n, Make
Make | make.com, integromat | Zapier
Workflow Automation | process automation | n8n, Zapier
WhatsApp Business API | whatsapp api, whatsapp automation, whatsapp business | Twilio, Chatbots
Chatbots | chatbot, conversational ai | LLM
Twilio | | WhatsApp Business API
Webhooks | webhook | REST
API Integration | api integrations | REST, Webhooks
Robotic Process Automation | rpa | Workflow Automation
""",
    "security": """
Linux | | Bash, Docker
Unix | | Linux
OAuth | oauth2, oauth 2.0 | JWT
JWT | json web token | OAuth
OWASP | | Cryptography
Cryptography | | OWASP
Cybersecurity | cyber security, information security, infosec | OWASP
eBPF | | Linux
Playwright | | Selenium
Selenium | | Playwright, Python
Cypress | | JavaScript
Pytest | | Python
Jest | | JavaScript
""",
    "it_support": """
Technical Support | tech support, technical support engineer | Troubleshooting, Customer Service
Troubleshooting | trouble shooting, problem solving, issue diagnosis | Root Cause Analysis, Technical Support
Help Desk | helpdesk, help-desk | Service Desk, Ticketing
Service Desk | servicedesk | Help Desk, ITIL
Desktop Support | end user support, end-user support | Windows, Hardware Troubleshooting
L1 Support | level 1 support, tier 1 support, l1 | L2 Support, Help Desk
L2 Support | level 2 support, tier 2 support, l2 | L1 Support
Ticketing | ticketing system, ticketing tools, ticket management | Help Desk, Zendesk
Incident Management | incident handling | ITIL, SLA Management
SLA Management | sla | Incident Management
ITIL | itil v4 | ITSM
ITSM | it service management | ITIL, ServiceNow
Remote Support | remote desktop support | TeamViewer, AnyDesk
TeamViewer | | Remote Support
AnyDesk | | Remote Support
Hardware Troubleshooting | hardware support, hardware | Desktop Support
Printer Support | printers | Hardware Troubleshooting
Windows | windows 10, windows 11, microsoft windows | Active Directory, Desktop Support
Windows Server | | Active Directory
macOS | mac os, os x | Desktop Support
Active Directory | ad | Group Policy, Windows Server
Group Policy | gpo | Active Directory
Microsoft 365 | office 365, o365, m365, microsoft office | Active Directory, Exchange
Exchange | exchange online, microsoft exchange | Microsoft 365
Intune | microsoft intune | Endpoint Management
Endpoint Management | mdm, sccm | Intune
Networking | computer networking, network troubleshooting | TCP/IP, DNS, LAN
LAN | | Networking
WAN | | Networking
TCP/IP | tcpip | Networking, DNS
DNS | | TCP/IP
DHCP | | DNS, TCP/IP
VPN | | Networking
Wi-Fi | wifi, wireless networking | Networking
Firewall | firewalls | Networking, Cybersecurity
Backup and Recovery | data backup, backup | Windows Server
Knowledge Base | knowledge base articles, kb articles | Documentation
Documentation | technical documentation | Knowledge Base
Root Cause Analysis | rca | Troubleshooting
""",
    "customer": """
Customer Service | customer support, customer care | Technical Support, CRM
Customer Success | | Customer Retention
Customer Retention | | Churn Reduction
Churn Reduction | | Customer Retention
Zendesk | | Freshdesk, Ticketing
Freshdesk | | Zendesk, Zoho Desk
Zoho Desk | | Freshdesk
Zoho CRM | zoho | CRM, Zoho Desk
ServiceNow | | ITSM
Jira Service Management | jira service desk | ITSM
CRM | crm systems, crm software | Salesforce, HubSpot, Zoho CRM
Salesforce | sfdc | CRM
HubSpot | | CRM, Email Marketing
CSAT | customer satisfaction | NPS
NPS | net promoter score | CSAT
Escalation Management | escalation handling | Incident Management
Client Onboarding | customer onboarding | Customer Success
Communication Skills | communication, written communication, verbal communication | Customer Service
Cloud Computing | cloud-based technologies, cloud technologies, cloud platforms | AWS, Azure, GCP
SaaS | saas support | Cloud Computing
""",
    "data_bi": """
Data Analytics | data analysis | SQL, Tableau
Business Intelligence | bi | Tableau, Power BI
Tableau | | Power BI
Power BI | powerbi | Tableau, Excel
Looker | looker studio | BigQuery
Excel | microsoft excel, ms excel | Power BI
Google Analytics | ga4 | SEO
Statistics | | R
Data Visualization | data viz | Tableau
ETL | | Airflow, SQL
""",
    "product_marketing": """
Product Management | | Agile, Product Strategy
Product Strategy | | Product Management
Agile | | Scrum, Kanban
Scrum | | Agile
Kanban | | Agile
Jira | | Agile, Confluence
Confluence | | Jira
SEO | search engine optimization | Content Strategy, Google Analytics
Content Strategy | content marketing | SEO, Copywriting
Copywriting | | Content Strategy
Digital Marketing | | SEO, Google Ads
Google Ads | adwords | Digital Marketing
Email Marketing | | HubSpot
Social Media Marketing | social media | Digital Marketing
Lead Generation | lead gen | CRM
""",
}

# Terms that are also ordinary English words or single letters. They only count when the
# text uses the exact canonical casing AND sits in a skills-style context (list delimiter next
# to it) or another skill of the same category corroborates it.
AMBIGUOUS: frozenset[str] = frozenset(
    {"C", "R", "Go", "AI", "Spring", "Express", "Swift", "Make", "Hardware", "L1", "L2", "AD", "CV", "ML"}
)


def _parse() -> tuple[dict[str, dict[str, object]], dict[str, str], list[tuple[str, str]]]:
    skills: dict[str, dict[str, object]] = {}
    alias_to_canon: dict[str, str] = {}
    edges: list[tuple[str, str]] = []
    for category, block in _RAW.items():
        for line in block.strip().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if not parts or not parts[0]:
                continue
            name = parts[0]
            aliases = [a.strip() for a in parts[1].split(",")] if len(parts) > 1 and parts[1] else []
            related = [r.strip() for r in parts[2].split(",")] if len(parts) > 2 and parts[2] else []
            skills[name] = {"category": category, "aliases": aliases}
            alias_to_canon[name.lower()] = name
            for alias in aliases:
                alias_to_canon[alias.lower()] = name
            edges.extend((name, r) for r in related if r)
    return skills, alias_to_canon, edges


TAXONOMY, ALIAS_TO_CANON, SEED_EDGES = _parse()
