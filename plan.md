# AI Security CTF Platform — Implementation Plan

## 1. Project Goal

Build a **local-first AI Security CTF platform** that runs entirely on Omar's Linux machine.

The platform should provide:

- A web interface for browsing CTF challenges.
- A dedicated challenge page for each challenge.
- An interactive AI/security lab environment.
- Flag submission.
- Deterministic flag validation.
- Solve tracking.
- Basic local scoring/progress.
- A clean architecture that can later support many challenges.
- No public hosting, cloud deployment, accounts, or multiplayer requirements for the first version.

### First milestone

Implement **one complete challenge end-to-end**.

Do not build 20 challenges before the platform works. The first challenge should prove the architecture of the entire platform.

---

# 2. Source Material and Design Direction

The AI Security Diploma covers areas including:

- AI system architecture and threats
- Data integrity and poisoning
- Input manipulation and adversarial attacks
- Prompt injection and jailbreaking
- Model extraction and interface security
- AI privacy and data leakage
- AI supply-chain security
- Runtime/production security
- APIs and governance
- MCP security
- Agentic AI security
- Red teaming
- CTF labs

The diploma explicitly positions the practical portion around hands-on AI security, red teaming, CTF labs, and building secure AI agents.

The teaching-lab reference establishes several useful engineering principles:

1. One challenge should have a clearly defined learning objective.
2. The vulnerability should be architectural rather than simply "find a magic prompt."
3. Other attack surfaces should be hardened where possible so the intended vulnerability is clear.
4. The success condition must be deterministic and checked by application code.
5. The flag should not depend on an LLM deciding that the player has solved the challenge.
6. The platform should make the attack path and root cause understandable after solving.

We will **not copy the example labs**.

Do not implement:

- The Academic Gateway/system-prompt-secret scenario.
- The Financial Clearance/prompt-as-authorization scenario.
- The Academic Record/appeal-note indirect-injection scenario.
- Segmented flags released by model-controlled sequencing.
- Any challenge whose solution is simply asking the model to reveal its system prompt.

Instead, the first challenge will introduce a different AI-security concept.

---

# 3. First Challenge Concept

## Challenge name

**Model Mirror**

## Category

**Model Extraction / Interface Security**

## Difficulty

**Beginner → Intermediate**

## Core vulnerability

**Model extraction through an overly informative prediction API.**

The challenge simulates an internal AI classification service exposed through a web/API interface.

The application owner believes that the model is protected because:

- the model weights are not downloadable;
- the model itself is running on the server;
- users only receive prediction results.

However, the API exposes enough information through repeated queries that a student can reconstruct useful information about the hidden model.

The challenge is intentionally simplified so that it can run locally without requiring a large ML model.

### Important distinction

This is **not** intended to be a realistic large-scale model-stealing attack requiring thousands of requests or GPU infrastructure.

It is a controlled educational simulation demonstrating the architectural principle:

> Protecting model weights is not sufficient if the model interface leaks too much information.

---

# 4. Challenge Story

The player is given access to a fictional company's "ContentShield" AI API.

ContentShield classifies submitted text into:

- `SAFE`
- `REVIEW`
- `BLOCK`

The company claims:

> "Our proprietary classifier is private. Users cannot access or download the model."

The API accepts text and returns a prediction plus confidence information.

The student's goal is to discover what the API unintentionally reveals and use that information to reproduce enough of the hidden decision boundary to trigger the flag.

The flag is awarded by application code after the player demonstrates the required behavior.

---

# 5. Intended Learning Objective

After completing the challenge, the student should understand:

- What model extraction is.
- Why inference APIs are part of the model's attack surface.
- Why excessive prediction information can leak model behavior.
- Why rate limiting alone is not a complete defense.
- Why confidence/probability information should be exposed carefully.
- Why protecting model files does not necessarily protect the model's intellectual property.
- How an attacker can treat a prediction API as an oracle.
- How defensive API design reduces extraction risk.

This connects naturally to the diploma's:

- Model Extraction & Interface Security & IP Protection
- APIs Governance
- AI Privacy Risks
- Runtime & Production Security

---

# 6. Challenge Architecture

Use a simple architecture:

```text
┌─────────────────────┐
│     Browser UI      │
│                     │
│ Challenge Page      │
│ API Console         │
│ Flag Submission     │
└──────────┬──────────┘
           │ HTTP
           ▼
┌─────────────────────┐
│     CTF Backend     │
│                     │
│ Challenge API       │
│ Session/Progress    │
│ Flag Validator      │
│ Solve Tracker       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  ContentShield      │
│  Inference Service  │
│                     │
│ Hidden classifier   │
│ Prediction logic    │
│ Confidence output   │
└─────────────────────┘
```

For the first version, these can all run as local processes/containers.

Do not introduce unnecessary microservices.

---

# 7. Recommended Technology Stack

Use a stack that is easy to run and modify on Linux.

## Frontend

**Next.js + TypeScript**

Use:

- Next.js App Router
- TypeScript
- Tailwind CSS
- Simple responsive UI

The frontend should provide:

- challenge list
- challenge details
- interactive API console
- request history
- flag submission
- solve state

## Backend

**Python + FastAPI**

Reasons:

- excellent for security-lab APIs;
- easy integration with ML/scientific Python;
- simple REST endpoints;
- easy local development;
- easy future expansion.

## Database

**SQLite**

For the first version.

Store:

- challenges
- player/session state
- submissions
- solves
- challenge state if required

Do not introduce PostgreSQL yet.

## Model / simulation

Use a **small deterministic local classifier**.

Possible implementation:

- scikit-learn model, or
- a deliberately constructed classifier.

Prefer a small deterministic model so:

- startup is fast;
- no internet is required;
- no external API key is required;
- results are reproducible;
- Claude can easily test it.

## Local execution

Support:

```bash
docker compose up
```

and preferably also:

```bash
./dev.sh
```

for developers who do not want Docker.

---

# 8. Repository Structure

Create the project approximately like this:

```text
ai-security-ctf/
│
├── README.md
├── plan.md
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── frontend/
│   ├── package.json
│   ├── next.config.ts
│   ├── app/
│   │   ├── page.tsx
│   │   ├── challenges/
│   │   │   ├── page.tsx
│   │   │   └── [slug]/
│   │   │       └── page.tsx
│   │   └── api/
│   ├── components/
│   └── lib/
│
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routes/
│   │   ├── services/
│   │   └── challenges/
│   │       └── model_mirror/
│   │           ├── challenge.py
│   │           ├── model.py
│   │           ├── validator.py
│   │           └── README.md
│   └── tests/
│
├── challenges/
│   └── model-mirror/
│       ├── README.md
│       ├── metadata.yaml
│       ├── author-notes.md
│       └── solution.md
│
├── scripts/
│   ├── seed.py
│   └── reset_db.py
│
└── docs/
    ├── architecture.md
    └── challenge-authoring.md
```

Keep challenge-specific logic isolated.

The platform should not need to know the internal details of every challenge.

---

# 9. Platform Data Model

## Challenge

Fields:

```text
id
slug
title
description
category
difficulty
points
author
is_active
created_at
updated_at
```

Example:

```text
slug: model-mirror
title: Model Mirror
category: Model Extraction
difficulty: intermediate
points: 100
```

## Player/session

For local MVP, do not implement full authentication.

Use a generated local player/session ID.

Fields:

```text
id
display_name
created_at
```

A default player can be created automatically.

## Submission

Fields:

```text
id
player_id
challenge_id
submitted_flag
is_correct
created_at
```

## Solve

Fields:

```text
id
player_id
challenge_id
solved_at
```

Add a unique constraint:

```text
(player_id, challenge_id)
```

so a challenge is only solved once.

---

# 10. Challenge API

The platform should expose generic challenge endpoints.

Example:

```http
GET /api/challenges
```

Returns active challenges.

```http
GET /api/challenges/{slug}
```

Returns public challenge metadata.

```http
POST /api/challenges/{slug}/submit
```

Checks a submitted flag.

Example request:

```json
{
  "player_id": "local-player",
  "flag": "OWASP{...}"
}
```

Example response:

```json
{
  "correct": true,
  "solved": true,
  "message": "Challenge solved."
}
```

Do not return the actual flag in API responses.

---

# 11. Challenge-Specific API

The Model Mirror challenge should have a separate inference endpoint.

Example:

```http
POST /api/challenges/model-mirror/predict
```

Request:

```json
{
  "text": "some text"
}
```

Response:

```json
{
  "label": "REVIEW",
  "confidence": 0.731,
  "probabilities": {
    "SAFE": 0.11,
    "REVIEW": 0.731,
    "BLOCK": 0.159
  }
}
```

The exact response should be intentionally informative.

This is part of the vulnerability.

---

# 12. The Hidden Model

The model must be deterministic.

Do not use an external OpenAI/Anthropic/Gemini API.

Do not require an internet connection.

Use a small local model.

Example conceptual setup:

```text
Input text
   ↓
Feature extraction
   ↓
Small classifier
   ↓
SAFE / REVIEW / BLOCK
   ↓
Confidence + class probabilities
```

The model should contain a hidden classification boundary that is not directly shown to the player.

The challenge documentation should explain the model at a high level but should not reveal the exact internal parameters.

---

# 13. Designing the Vulnerability

The vulnerable interface should expose:

1. predicted class;
2. confidence;
3. class probability distribution;
4. unlimited or insufficiently restricted inference requests during the challenge.

The combination allows the player to query the classifier repeatedly.

The student should eventually infer enough of the model's behavior to construct a special input that causes a specific target classification.

That target classification is the deterministic solve condition.

---

# 14. Deterministic Solve Condition

Do NOT have the LLM judge whether the player solved the challenge.

Do NOT inspect natural-language explanations.

The backend should check a concrete condition.

Example:

```text
If the player submits an inference request that satisfies
the hidden target classification and the required behavioral
conditions, mark the challenge as solved.
```

For example, the backend can require:

```text
target_label == BLOCK
AND
target confidence >= threshold
AND
input belongs to the intended challenge target
```

The exact condition should be implemented in code.

The flag should be generated/returned only by the challenge validator after the condition is met.

---

# 15. Better Challenge Mechanism

Do not simply make the flag:

```text
OWASP{MODEL_EXTRACTION}
```

Instead generate a challenge-specific random-looking flag during setup.

Example:

```text
OWASP{mirror_<random_suffix>}
```

Store its hash rather than relying on the frontend.

The challenge validator should know the expected solve state.

The player must still submit the flag through the platform.

Recommended flow:

```text
Player discovers vulnerability
        ↓
Player reaches intended model behavior
        ↓
Challenge backend marks state as solved
        ↓
Backend exposes the flag to the solved player
        ↓
Player submits flag
        ↓
Platform records solve
```

This combines deterministic solve detection with explicit flag submission.

---

# 16. Avoiding Accidental Alternative Solutions

The challenge must be tested against obvious shortcuts.

Claude should create automated tests for:

### Prompt injection

If the model is not an LLM, prompt injection should not be relevant.

Do not accidentally add an LLM merely because this is an AI-security CTF.

### Direct flag retrieval

The flag must not exist in:

- frontend source;
- public challenge metadata;
- API documentation;
- browser JavaScript;
- database rows readable by the challenge API;
- Docker environment variables exposed to the player.

### Directory traversal

Do not expose arbitrary files.

### Debug endpoints

Disable:

```text
/docs
/redoc
/openapi.json
```

in production-like challenge mode, or ensure they do not expose secrets.

For local development they may remain enabled behind a development setting.

### SQL injection

The first challenge should not accidentally become an SQL injection challenge.

Use parameterized queries/ORM.

### Authentication bypass

The MVP does not need complex authentication.

Do not make authentication the intended challenge.

---

# 17. Challenge UI

The challenge page should contain:

## Header

```text
Model Mirror
Model Extraction
100 Points
Intermediate
```

## Description

Explain the scenario without revealing the solution.

## Objective

Example:

```text
ContentShield claims that its proprietary model is impossible
to reproduce because the model weights never leave the server.

Prove that claim wrong.

Your objective is to discover enough information about the
model through its public prediction interface to reproduce
the target behavior.
```

## API Console

Provide:

```text
Input text:
[                                  ]

[ Run Prediction ]
```

Show:

```text
Label
Confidence
Class probabilities
Request number
```

## Request history

Display previous requests.

This is useful for learning and experimentation.

## Flag submission

```text
Flag:
[                                  ]

[ Submit Flag ]
```

## Challenge status

```text
Status: Not Solved
```

After solving:

```text
Status: Solved
```

---

# 18. Platform Homepage

The homepage should be simple.

Example:

```text
OMAR WEB3
AI SECURITY CTF

Learn AI security by breaking vulnerable systems.

[ View Challenges ]
```

Then show:

```text
1 Challenge
100 Total Points
0 Solved
```

Do not over-design the MVP.

---

# 19. Challenge Listing

Example:

```text
Challenges

┌────────────────────────────────────┐
│ Model Mirror                       │
│ Model Extraction                   │
│ Intermediate                       │
│ 100 Points                         │
│                                    │
│ [Start Challenge]                  │
└────────────────────────────────────┘
```

Future challenges can reuse this component.

---

# 20. Flag Format

Use a consistent format:

```text
OWASP{...}
```

The exact flag for the first challenge should be generated during initialization.

Never put the plaintext flag in frontend code.

For a stronger implementation, store:

```text
SHA-256(flag)
```

and validate submissions against the hash.

---

# 21. Challenge Metadata

Use a YAML file:

```yaml
slug: model-mirror
title: Model Mirror
category: Model Extraction
difficulty: intermediate
points: 100

description: >
  Investigate a proprietary AI classifier whose inference
  interface reveals more information than intended.

learning_objectives:
  - Understand model extraction
  - Understand inference APIs as attack surfaces
  - Understand confidence leakage
  - Understand defensive API design

author: Omar Web3
```

The platform should load public metadata from this structure.

Do not put secrets in `metadata.yaml`.

---

# 22. Admin/Author Separation

Do not build an admin dashboard yet.

Challenge authors should be able to create a challenge by adding:

```text
challenges/<slug>/
```

with its own:

- metadata
- implementation
- validator
- documentation
- tests

Future versions can provide a UI for challenge authors.

---

# 23. Security Requirements for the Platform

Even though this is a CTF platform, the platform itself should be reasonably secure.

Implement:

- parameterized database queries;
- server-side flag validation;
- no secrets in frontend;
- no secrets in Git;
- environment variables for deployment configuration;
- request size limits;
- basic rate limiting;
- structured logging;
- safe error messages;
- input validation with Pydantic;
- CORS configured explicitly;
- no arbitrary command execution from challenge input.

Because this platform will initially run locally, prioritize simplicity over production-scale security infrastructure.

---

# 24. Local Development Requirements

The entire project must work on a normal Linux machine.

Target workflow:

```bash
git clone <repo>
cd ai-security-ctf

cp .env.example .env

docker compose up --build
```

Then open:

```text
http://localhost:3000
```

The backend should be available internally and, if useful for development:

```text
http://localhost:8000
```

The README must explain:

- prerequisites;
- installation;
- Docker startup;
- non-Docker startup;
- database initialization;
- how to reset the environment;
- how to run tests.

---

# 25. Docker Architecture

Use two containers initially:

```text
frontend
backend
```

SQLite can live inside the backend volume.

Do NOT create:

- Kubernetes;
- Redis;
- PostgreSQL;
- separate ML service;
- message queues;

unless they become necessary.

The goal is a simple local CTF platform.

---

# 26. Testing

Write tests before considering the challenge complete.

## Backend tests

Test:

- challenge listing;
- challenge lookup;
- valid flag;
- invalid flag;
- duplicate solve;
- unknown challenge;
- invalid inference input;
- inference response schema;
- deterministic inference output;
- challenge solve condition.

## Security tests

Test:

- flag is not exposed before solve;
- flag is not exposed through challenge metadata;
- flag is not exposed through frontend bundle;
- arbitrary files cannot be accessed;
- SQL injection attempts fail;
- malformed requests fail safely.

## Challenge tests

At minimum:

```text
normal user input
invalid input
empty input
very long input
special characters
unicode input
repeated requests
intended solve path
obvious shortcut attempts
```

---

# 27. Author Solution

Create:

```text
challenges/model-mirror/solution.md
```

This is for the challenge author, not the player.

It should contain:

1. Intended vulnerability.
2. Expected attack reasoning.
3. Example exploration.
4. Expected solve condition.
5. Exact remediation.
6. Common unintended solutions.
7. Testing instructions.

Do not expose `solution.md` through the web application.

---

# 28. Challenge Write-up Structure

Every future challenge should eventually use this structure:

```text
# Challenge Name

## Scenario

## Learning Objective

## Vulnerability

## Architecture

## Intended Attack Surface

## Hints

## Success Condition

## Remediation

## Author Notes
```

This makes the platform scalable as an educational product.

---

# 29. Hints System

For the MVP, support three hints.

Example:

```text
Hint 1 — Free
Look carefully at everything the prediction API returns.

Hint 2 — Costs 10 points
Ask yourself what information confidence values reveal.

Hint 3 — Costs 20 points
Treat the prediction endpoint as an oracle and study how
its output changes when you systematically modify inputs.
```

The actual hints should not reveal the complete solution.

The hint cost system can be implemented later if necessary.

For the first version, hints may simply be static.

---

# 30. Scoring

MVP scoring:

```text
Challenge points = 100
```

Optional future scoring:

```text
Base points
- Hint penalties
- Time bonus
- First blood
```

Do not implement complex competition scoring now.

---

# 31. Observability

The backend should log:

```text
timestamp
player_id
challenge
endpoint
request ID
result
```

For the Model Mirror challenge also log:

```text
prediction label
confidence
```

Do not log sensitive secrets.

Logs should help the author debug challenges and understand how students interact with them.

---

# 32. Reset Mechanism

Create:

```bash
python scripts/reset_db.py
```

or:

```bash
docker compose down -v
docker compose up --build
```

The README should clearly explain how to reset all local progress.

---

# 33. Definition of Done — Platform

The platform MVP is complete when:

- [ ] Frontend starts locally.
- [ ] Backend starts locally.
- [ ] SQLite database initializes automatically.
- [ ] Homepage works.
- [ ] Challenge listing works.
- [ ] Challenge detail page works.
- [ ] Player/session is created automatically.
- [ ] Flag submission works.
- [ ] Solves are persisted.
- [ ] Duplicate solves are handled.
- [ ] Challenge-specific API works.
- [ ] Docker Compose works from a clean checkout.
- [ ] Automated tests pass.

---

# 34. Definition of Done — Model Mirror

The first challenge is complete when:

- [ ] Challenge has a clear learning objective.
- [ ] Challenge is different from the provided teaching labs.
- [ ] No system-prompt leakage mechanism is used.
- [ ] No prompt-as-authorization mechanism is used.
- [ ] No indirect-prompt-injection/appeal-note mechanism is used.
- [ ] Model runs locally.
- [ ] Model is deterministic.
- [ ] Prediction API works.
- [ ] API exposes intentionally excessive information.
- [ ] Intended extraction path is reproducible.
- [ ] Solve condition is checked by code.
- [ ] Flag is not present in frontend source.
- [ ] Flag is not returned before the solve condition.
- [ ] Challenge has an author solution.
- [ ] Challenge has tests.
- [ ] Remediation is documented.

---

# 35. Future Challenge Roadmap

Do not implement these now.

They are possible future challenge families based on the diploma:

## Challenge 2 — Poisoned Dataset

Category:

```text
Data Poisoning
```

Concept:

A training pipeline trusts an unvalidated data source.

Students identify how a malicious training example changes the resulting model behavior.

---

## Challenge 3 — Agent Tool Confusion

Category:

```text
Agentic AI Security
```

Concept:

An agent has several tools with different trust levels.

The vulnerability should be something other than prompt-as-authorization.

---

## Challenge 4 — Retrieval Boundary

Category:

```text
AI Privacy / Data Leakage
```

Concept:

A retrieval layer accidentally returns information outside the intended tenant/document boundary.

The goal would be to reason about retrieval authorization rather than prompt manipulation.

---

## Challenge 5 — MCP Tool Poisoning

Category:

```text
MCP Security
```

Concept:

A malicious or compromised tool description influences an agent's tool-selection behavior.

The challenge should have explicit tool-level security controls and a deterministic success condition.

---

## Challenge 6 — Adversarial Input

Category:

```text
Adversarial ML
```

Concept:

A classifier behaves differently under carefully crafted perturbations.

---

## Challenge 7 — Supply Chain

Category:

```text
AI Supply Chain Security
```

Concept:

A model/package dependency contains an unexpected modification.

---

# 36. Important Design Rule for Future Challenges

Every challenge must answer these questions before implementation:

```text
1. What exactly is the vulnerability?

2. What architectural component contains the weakness?

3. What attack does the student perform?

4. Why does the attack work?

5. What other attack surfaces are intentionally closed?

6. What exact condition proves the challenge was solved?

7. How is the solve condition checked by code?

8. What is the correct remediation?

9. Could a student solve it accidentally using a different vulnerability?

10. Can the challenge run deterministically on a local machine?
```

If these questions cannot be answered, do not implement the challenge yet.

---

# 37. Claude Code Implementation Order

Claude should implement the project in this order.

## Phase 1 — Repository bootstrap

Create:

```text
frontend/
backend/
challenges/
scripts/
docs/
```

Add:

- Git configuration;
- `.env.example`;
- README;
- Docker Compose;
- development commands.

Do not implement the challenge yet.

---

## Phase 2 — Backend foundation

Implement:

- FastAPI app;
- configuration;
- SQLite;
- database models;
- migrations/init;
- challenge registry;
- player/session;
- submission;
- solve tracking.

Write tests.

---

## Phase 3 — Frontend foundation

Implement:

- homepage;
- challenge listing;
- challenge page;
- flag submission;
- solve state;
- basic styling.

Use mocked challenge data only if needed during this phase.

---

## Phase 4 — Generic challenge interface

Create the abstraction that lets future challenges plug into the platform.

For example:

```python
class Challenge:
    slug: str
    title: str
    category: str
    difficulty: str
    points: int

    def initialize(self):
        ...

    def check_solve(self, state):
        ...

    def get_public_metadata(self):
        ...
```

Do not over-engineer this interface.

The first challenge should determine what abstraction is actually necessary.

---

## Phase 5 — Implement Model Mirror

Implement:

```text
model.py
challenge.py
validator.py
```

Build the deterministic classifier.

Build the prediction endpoint.

Build the intended extraction path.

Build the solve condition.

Write challenge-specific tests.

---

## Phase 6 — Connect frontend

Add the interactive prediction console.

The browser should call:

```text
POST /api/challenges/model-mirror/predict
```

Display results clearly.

Add:

- request history;
- challenge status;
- flag submission.

---

## Phase 7 — Security review

Perform a manual and automated review.

Attempt:

- direct flag discovery;
- source inspection;
- API enumeration;
- malformed inputs;
- SQL injection;
- path traversal;
- excessive request payloads;
- replay;
- duplicate submissions;
- unintended challenge shortcuts.

---

## Phase 8 — Documentation

Complete:

```text
README.md
docs/architecture.md
docs/challenge-authoring.md
challenges/model-mirror/README.md
challenges/model-mirror/solution.md
```

README must contain exact Linux setup instructions.

---

# 38. Claude Code Instructions

When implementing this plan:

### Do

- Keep the project local-first.
- Keep the architecture simple.
- Use deterministic behavior.
- Write tests alongside implementation.
- Keep challenge logic isolated.
- Keep secrets server-side.
- Make the first challenge fully playable before expanding the platform.
- Prefer simple code over unnecessary abstractions.
- Document important security decisions.

### Do not

- Host anything publicly.
- Add cloud services.
- Require paid APIs.
- Require OpenAI/Anthropic/Gemini API keys.
- Copy the attached teaching labs.
- Reimplement the three example scenarios.
- Make the flag depend on LLM judgment.
- Put the flag in frontend code.
- Build an admin dashboard.
- Build multiplayer functionality.
- Build a ranking/leaderboard system yet.
- Build Kubernetes infrastructure.
- Over-engineer the challenge framework.

---

# 39. Final MVP User Journey

A user should be able to do this from a clean Linux machine:

```text
1. Start the project

   docker compose up --build

2. Open

   http://localhost:3000

3. See

   Omar Web3 AI Security CTF

4. Click

   Model Mirror

5. Read the scenario

6. Experiment with the prediction API

7. Discover the information leakage

8. Perform the intended model-extraction reasoning

9. Reach the deterministic solve condition

10. Receive the flag

11. Submit the flag

12. See:

   Challenge Solved
   100 Points
```

That is the first milestone.

Only after this complete flow works reliably should additional challenges be added.
