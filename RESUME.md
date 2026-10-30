# Alex Chen
San Francisco, CA | (415) 555-0192 | alex.chen.eng@gmail.com  
[github.com/alexchen-dev](https://github.com) | [linkedin.com/in/alexchen-eng](https://linkedin.com)

---

## PROFESSIONAL SUMMARY
Senior Software & AI Infrastructure Engineer with 5+ years of experience architecting high-throughput distributed backends, LLM-powered RAG systems, and cloud-native microservices serving millions of daily active users. Expert in Python, FastAPI, PyTorch, AWS, and database optimization.

---

## TECHNICAL SKILLS
* **Languages:** Python, TypeScript, Go, SQL, C++, Bash
* **Frameworks & AI:** FastAPI, PyTorch, Django, LangChain, Hugging Face Transformers, Celery, gRPC
* **Databases & Caching:** PostgreSQL, Redis, SQLite (FTS5), Elasticsearch, MongoDB
* **Cloud & DevOps:** AWS (ECS, EKS, Lambda, S3, RDS), Docker, Kubernetes, Terraform, GitHub Actions, Linux
* **Architecture & Systems:** Distributed Systems, RESTful APIs, Microservices, Hybrid RAG, Reciprocal Rank Fusion, High Concurrency

---

## PROFESSIONAL EXPERIENCE

### Senior AI & Backend Infrastructure Engineer
**Nexus Cloud Systems** | San Francisco, CA  
*March 2022 – Present*
* Architected and deployed an asynchronous hybrid search microservice using FastAPI, PostgreSQL, and Redis, reducing P99 query latency by 42% for 2.4M+ daily active requests.
* Spearheaded migration from monolithic services to containerized Kubernetes microservices on AWS EKS, cutting monthly cloud infrastructure expenditure by 30%.
* Designed real-time embedding retrieval pipelines integrating PyTorch and FAISS, boosting search precision from 71% to 94% across enterprise knowledge bases.
* Built automated, zero-downtime CI/CD deployment pipelines using GitHub Actions, reducing production release duration from 45 minutes to under 6 minutes.
* Mentored a distributed team of 6 engineers on type safety, asynchronous architecture, and automated test-driven development.

### Backend Software Engineer
**DataPulse Analytics** | Austin, TX (Remote)  
*June 2020 – February 2022*
* Engineered scalable data ingestion pipelines in Python and Celery processing over 15M event records per day with zero data loss.
* Optimized PostgreSQL database indexing and implemented distributed Redis caching strategies, improving overall system throughput by 3.5x.
* Developed secure, OAuth 2.0-compliant public REST and gRPC API endpoints consumed by 40+ external enterprise clients.
* Instituted comprehensive unit and integration test suites using Pytest, driving test coverage from 52% to 91%.

---

## KEY PROJECTS

### Distributed Real-Time Semantic Search & RRF Engine
*Tech Stack:* Python, FastAPI, SQLite FTS5, PyTorch, Docker  
* [github.com/alexchen-dev/hybrid-rrf-engine](https://github.com)
* Implemented a hybrid lexical BM25 and dense vector search engine utilizing Reciprocal Rank Fusion ($k=60$) for ultra-low latency text ranking.
* Achieved sub-15ms retrieval across 500,000 documents with an in-process SQLite FTS5 Porter tokenizer and vector cosine store.

### Scalable Cloud Task Orchestrator
*Tech Stack:* Go, Redis, Docker, Terraform, AWS  
* [github.com/alexchen-dev/task-orchestrator](https://github.com)
* Built an event-driven background task scheduling worker cluster supporting dynamic priority queues and worker failure recovery.
* Automated full cloud provisioning and IAM security policies using Terraform.

---

## EDUCATION

### B.S. in Computer Science
**University of California, Berkeley**  
*Graduated: May 2020*  
* Focus: Distributed Systems & Machine Learning Algorithms
