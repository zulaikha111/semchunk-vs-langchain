"""
Sample dataset for chunking comparison.

Design principles:
- Documents WITH newlines test the baseline (both chunkers split on \\n first)
- Documents WITHOUT newlines expose the real algorithmic differences
- Each document comment explains what specific behavior it tests
- No artificial bias toward either chunker

Key algorithmic difference:
  LangChain separators: ["\\n\\n", "\\n", " ", ""]
  semchunk: newlines > tabs > spaces-after-punctuation > punctuation > characters

  When text has spaces, BOTH split on spaces. But semchunk preferentially
  splits at spaces that follow structurally meaningful punctuation (. ; , — etc),
  while LangChain splits at whichever space is nearest to the token limit.

  When text has NO spaces, semchunk falls through to punctuation splitters
  (. ; , ( ) / - etc), while LangChain falls through to "" (character-level).
"""

DOCUMENTS = {
    # ---------------------------------------------------------------
    # BASELINE: Well-structured text with newlines
    # Expected: Both chunkers produce identical or near-identical output
    # ---------------------------------------------------------------
    "structured_markdown": """# Database Indexing Guide

## Introduction

Database indexing is one of the most important concepts in database management. An index is a data structure that improves the speed of data retrieval operations on a database table at the cost of additional writes and storage space. Without indexes, the database must scan every row in a table to find the relevant data.

## How B-Tree Indexes Work

The most common type of index is the B-tree (balanced tree) index. A B-tree maintains sorted data and allows searches, sequential access, insertions, and deletions in logarithmic time.

When you create an index on a column, the database builds a B-tree where each internal node contains keys and pointers to child nodes. Leaf nodes contain the actual index entries pointing to table rows. The tree stays balanced through split and merge operations.

## Composite Indexes

A composite index includes multiple columns. The order of columns matters significantly due to the leftmost prefix rule.

```sql
CREATE INDEX idx_name_age ON users(last_name, first_name, age);

-- Can efficiently support:
SELECT * FROM users WHERE last_name = 'Smith';
SELECT * FROM users WHERE last_name = 'Smith' AND first_name = 'John';

-- Cannot efficiently support (skips leftmost column):
SELECT * FROM users WHERE first_name = 'John' AND age > 25;
```

## Trade-offs

While indexes speed up reads, they slow down writes. Every INSERT, UPDATE, or DELETE must also update all relevant indexes. For write-heavy workloads, too many indexes can degrade performance significantly.""",

    # ---------------------------------------------------------------
    # TEST: Dense prose with sentence boundaries (spaces present)
    # Tests: semchunk's "space after punctuation" preference
    # Expected: semchunk splits at sentence boundaries (space after period),
    #           LangChain splits at nearest space to token limit
    # ---------------------------------------------------------------
    "dense_prose_sentences": """The evolution of machine learning has been nothing short of remarkable. Starting from simple perceptrons in the 1950s, the field has grown to encompass deep neural networks with billions of parameters. Transformer architectures have revolutionized natural language processing. Diffusion models can generate photorealistic images from text descriptions. The key breakthrough came in 2017 when Vaswani et al. published their landmark paper introducing the transformer architecture that replaced recurrent neural networks with self-attention mechanisms. This allowed for much greater parallelization during training, enabling models to be trained on vastly larger datasets than was previously feasible. The implications were profound. Within just a few years, models like BERT and GPT demonstrated capabilities that many researchers had not expected to see for decades, including few-shot learning and chain-of-thought reasoning. Meanwhile, in computer vision, the introduction of Vision Transformers showed that the same architecture could achieve state-of-the-art results on image classification tasks. This convergence of architectures across modalities has led to the development of multimodal models that can process text, images, audio, and video within a single unified framework. The scaling laws discovered by Kaplan et al. revealed a surprisingly predictable relationship between model size, dataset size, compute budget, and model performance. However, this approach faces fundamental challenges including enormous energy consumption, the difficulty of curating high-quality training data at scale, and the challenge of aligning model behavior with human values and intentions.""",

    # ---------------------------------------------------------------
    # TEST: Dense prose with semicolons as clause separators (spaces present)
    # Tests: semchunk's preference for spaces after semicolons
    # Expected: semchunk splits at clause boundaries (space after ;),
    #           LangChain splits at nearest space to token limit
    # ---------------------------------------------------------------
    "dense_prose_semicolons": """The server infrastructure required a complete overhaul; the legacy systems were running on end-of-life hardware that could no longer receive security patches; the network topology had grown organically over fifteen years without any coherent architecture; the monitoring stack was a patchwork of incompatible tools that generated thousands of false alerts daily; the deployment process required manual intervention at seven different stages and took an average of four hours to complete; the disaster recovery plan had never been tested and relied on assumptions about data center availability that were no longer valid; the team had accumulated significant technical debt by repeatedly choosing quick fixes over proper solutions; the documentation was scattered across wikis, shared drives, and individual engineers' notebooks with no single source of truth; the on-call rotation was burning out senior engineers who were the only ones with enough institutional knowledge to troubleshoot production issues; and the budget for infrastructure improvements had been cut three years in a row in favor of feature development.""",

    # ---------------------------------------------------------------
    # TEST: Literary prose with em-dashes and ellipses (spaces present)
    # Tests: semchunk's preference for spaces after em-dashes (—) and
    #        ellipses (…), which it classifies as sentence interrupters
    # Expected: semchunk splits at natural parenthetical boundaries,
    #           LangChain splits at nearest space to token limit
    # ---------------------------------------------------------------
    "literary_emdash": """The old house at the end of Maple Street had been abandoned for years \u2014 or so everyone believed \u2014 but on certain autumn evenings, when the fog rolled in from the harbor and the streetlights cast their amber glow through the bare branches of the elm trees, you could see a faint light flickering in the upstairs window\u2026 just for a moment\u2026 then gone. Mrs. Henderson \u2014 who had lived next door for forty-three years and who remembered when the Whitfield family still occupied the place \u2014 swore she heard piano music drifting through the walls on Tuesday nights, always Chopin, always the same nocturne. The neighborhood children \u2014 braver than their parents, as children often are \u2014 had their own theories about what lurked inside. None of them had ever actually entered the house\u2026 not because they were afraid, they would insist, but because the front door was always locked and the windows were boarded shut. The real estate agent \u2014 a cheerful woman named Patricia who had been trying to sell the property for the better part of a decade \u2014 had a more mundane explanation. She would say the light was probably a reflection from passing cars, the music was likely from Mrs. Henderson's own radio, and the house was simply\u2026 unsellable.""",

    # ---------------------------------------------------------------
    # TEST: CSV-like data WITHOUT spaces (only commas and semicolons)
    # Tests: semchunk's punctuation-level splitting vs LangChain's
    #        character-level fallback when no spaces exist
    # Expected: semchunk splits at ; (record boundaries), keeping records intact
    #           LangChain falls through to "" and splits at character boundaries
    # THIS IS THE BIGGEST DIFFERENTIATOR
    # ---------------------------------------------------------------
    "csv_no_spaces": """id,name,dept,salary,start_date,office,manager_id,status;1001,James.Morrison,Engineering,145000,2019-03-15,Seattle-HQ-Floor12,1000,active;1002,Sarah.Chen,Engineering,178000,2017-08-22,Seattle-HQ-Floor12,1000,active;1003,Michael.OBrien,Product,155000,2020-01-10,Seattle-HQ-Floor8,1050,active;1004,Priya.Patel,Engineering,125000,2021-06-01,Austin-Office-Floor3,1001,active;1005,David.Kim,Design,140000,2018-11-30,Seattle-HQ-Floor8,1050,active;1006,Maria.Garcia,Engineering,135000,2020-09-14,Seattle-HQ-Floor12,1002,active;1007,Robert.Johnson,DataScience,160000,2019-07-08,NYC-Office-Floor5,1060,active;1008,Lisa.Wang,Engineering,195000,2016-02-28,Seattle-HQ-Floor12,1000,active;1009,Ahmed.Hassan,Security,142000,2021-03-20,Seattle-HQ-Floor15,1070,active;1010,Jennifer.Taylor,Engineering,110000,2023-01-09,Austin-Office-Floor3,1001,active""",

    # ---------------------------------------------------------------
    # TEST: URL/path-heavy text WITHOUT spaces
    # Tests: semchunk's word-joiner splitting (/ \ - &) vs LangChain's
    #        character-level fallback
    # Expected: semchunk splits at / boundaries within paths,
    #           LangChain splits at arbitrary character positions
    # ---------------------------------------------------------------
    "paths_no_spaces": """s3://prod-artifacts-us-east-1/builds/api-gateway/2025/01/15/build-7842/api-gateway-2.4.1-SNAPSHOT.jar->123456789012.dkr.ecr.us-east-1.amazonaws.com/platform/api-gateway:2.4.1-build7842-sha-a1b2c3d4->arn:aws:eks:us-west-2:123456789012:cluster/staging-platform-cluster/namespaces/api-gateway-staging->https://grafana.internal.example.com/d/api-gateway-staging/api-gateway-overview?orgId=1&from=now-6h&to=now->arn:aws:secretsmanager:us-east-1:123456789012:secret:platform/api-gateway/production/database-credentials-AbCdEf->arn:aws:acm:us-east-1:123456789012:certificate/12345678-abcd-efgh-ijkl-123456789012""",

    # ---------------------------------------------------------------
    # TEST: Log entries WITHOUT newlines (spaces present)
    # Tests: semchunk's preference for spaces after colons and em-dashes
    # Expected: semchunk splits at log entry boundaries (after timestamps/levels),
    #           LangChain splits at nearest space to token limit
    # ---------------------------------------------------------------
    "server_logs_inline": """2025-01-15T09:00:01.234Z INFO [main] ApplicationBootstrap: Starting application server v2.4.1 in production mode with 4 worker threads and connection pool size 20. 2025-01-15T09:00:02.789Z INFO [main] DatabaseConnector: Primary database connection established successfully in 1333ms with pool size 20/20 available. 2025-01-15T09:00:03.234Z INFO [main] CacheManager: Redis connection established successfully with cluster mode enabled and 3 master nodes detected. 2025-01-15T09:00:03.678Z WARN [main] ConfigValidator: Deprecated configuration key detected in application.yml. 2025-01-15T09:00:03.890Z INFO [main] ApplicationBootstrap: Application server started successfully on 0.0.0.0:8443 in 2656ms. 2025-01-15T09:00:15.123Z INFO [worker-1] RequestHandler: POST /api/v2/users responded 201 Created in 45ms. 2025-01-15T09:00:16.789Z WARN [worker-1] RateLimiter: Client 10.0.2.100 approaching rate limit at 85/100 requests in current window. 2025-01-15T09:00:17.012Z ERROR [worker-3] RequestHandler: GET /api/v2/products/9999 responded 500 Internal Server Error in 234ms. 2025-01-15T09:00:17.234Z ERROR [worker-3] AlertManager: Critical error threshold reached for endpoint /api/v2/products with 5 errors in last 60 seconds.""",

    # ---------------------------------------------------------------
    # TEST: Dense list without newlines (spaces present)
    # Tests: semchunk's preference for spaces after periods
    # Expected: semchunk splits at sentence boundaries,
    #           LangChain splits at nearest space
    # ---------------------------------------------------------------
    "dense_checklist": """System Design Interview Checklist: Requirements Gathering. Ask about functional requirements and what the system should do. Ask about non-functional requirements including latency, throughput, availability, and consistency. Clarify the scale including how many users and how many requests per second. Ask about read vs write ratio. Ask about data retention requirements. Back-of-the-Envelope Estimation. Calculate storage needs based on data model and retention. Estimate bandwidth requirements for peak traffic. Calculate the number of servers needed based on throughput requirements. Consider caching hit ratios and their impact on backend load. Factor in replication overhead for high availability. High-Level Design. Start with a simple client-server architecture. Identify the core entities and their relationships. Design the API endpoints. Choose between SQL and NoSQL based on data access patterns. Add a load balancer for horizontal scaling. Introduce caching layer for frequently accessed data. Add a message queue for asynchronous processing. Detailed Design. Design the database schema with proper indexing strategy. Implement consistent hashing for distributed caching. Design the data partitioning strategy. Implement rate limiting to prevent abuse. Design the notification system. Implement circuit breakers for external service calls.""",

    # ---------------------------------------------------------------
    # TEST: Nested academic citations (spaces present, heavy parentheses)
    # Tests: whether semchunk's parenthesis-aware splitting helps or hurts
    # Expected: mixed results — parentheses may cause over-fragmentation
    # ---------------------------------------------------------------
    "academic_citations": """The relationship between sleep duration and cognitive performance (as measured by the Montreal Cognitive Assessment and the Mini-Mental State Examination) has been extensively studied in older adults (aged 65 and above) across multiple longitudinal cohorts (including the Framingham Heart Study with 2457 participants and mean follow-up of 8.3 years, the Rotterdam Study with 4215 participants and mean follow-up of 11.1 years, and the Whitehall II Study with 5123 participants and mean follow-up of 15.2 years). The findings consistently demonstrate a U-shaped association (see Figure 3a for unadjusted and adjusted models) whereby both short sleepers (defined as those reporting fewer than 6 hours of sleep per night by self-report or fewer than 5.5 hours by actigraphy) and long sleepers (defined as those reporting more than 9 hours per night by self-report or more than 8.5 hours by actigraphy) exhibited significantly greater cognitive decline compared to the reference group of 7 to 8 hours per night. Notably, the effect was more pronounced in carriers of the APOE-epsilon-4 allele (interaction term p equals 0.003 after Bonferroni correction) and in participants with pre-existing mild cognitive impairment, suggesting that these subgroups may be particularly vulnerable to the neurocognitive effects of suboptimal sleep duration.""",
}
