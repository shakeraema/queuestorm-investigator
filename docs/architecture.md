# Technical Architecture Document

This document describes the design patterns, component relationships, lifecycle, and deployment structure for **QueueStorm Investigator**.

---

## 1. High-Level Flowchart (Request Routing and Processing)

This flowchart illustrates the step-by-step processing of a support ticket from initial API payload parsing to final safety validation.

```mermaid
graph TD
    Client([Client HTTP Request]) -->|POST /analyze-ticket| Main[FastAPI App router: app/main.py]
    
    subgraph Request Validation & Auditing
        Main -->|Validate Schema| SchemaCheck{Pydantic Schema Valid?}
        SchemaCheck -->|No| Err400[Return 400 Bad Request]
        SchemaCheck -->|Yes| PromptInjectionCheck{Prompt Injection?}
        PromptInjectionCheck -->|Yes| SecurityOverride[Apply Security Override]
    end

    subgraph Investigation Engine Pipeline
        PromptInjectionCheck -->|No| Matcher[Transaction Matcher: app/services/matcher.py]
        Matcher -->|Scoring Heuristics| EntityExtraction[Extract Amounts/Phones/Types]
        EntityExtraction -->|Match History| MatchVerdict{Tx ID Matched?}
        
        MatchVerdict -->|Consistent| ConsistentVerdict[Verdict: consistent]
        MatchVerdict -->|Inconsistent| InconsistentVerdict[Verdict: inconsistent]
        MatchVerdict -->|Ambiguous / None| InsufficientVerdict[Verdict: insufficient_data]
        
        ConsistentVerdict & InconsistentVerdict & InsufficientVerdict --> Classifier[Case Classifier: app/services/classifier.py]
        Classifier -->|Determine Metadata| ClassRules[Map case_type, severity, department, human_review]
        
        ClassRules --> Generator[Response Generator: app/services/generator.py]
        Generator -->|Fill templates / LLM| TextGen[Generate internal summaries & replies]
    end

    subgraph Post-Audit Safety Guardrails
        SecurityOverride & TextGen --> SafetyEngine[Safety Engine: app/core/safety.py]
        SafetyEngine -->|Verify Sentences| SafetyAudit{Passes safety regex?}
        SafetyAudit -->|No| Sanitizer[Apply Safe Fallback Templates]
        SafetyAudit -->|Yes| ResponseBuilder[Build TicketAnalysisResponse]
        Sanitizer --> ResponseBuilder
    end

    ResponseBuilder --> ClientResponse([Client HTTP Response 200 OK])
```

---

## 2. Sequence Diagram (Request Lifecycle)

This diagram details the object interactions and execution sequence for a typical analysis call.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client / Judge
    participant Main as FastAPI Main Router
    participant Safety as Safety Engine
    participant Matcher as Transaction Matcher
    participant Classifier as Case Classifier
    participant Generator as Response Generator

    Client->>Main: POST /analyze-ticket (payload JSON)
    activate Main
    Main->>Main: Pydantic Validation Check
    Main->>Safety: detect_prompt_injection(complaint)
    activate Safety
    Safety-->>Main: is_injection (boolean)
    deactivate Safety
    
    alt is_injection is True
        Main->>Main: Build Security Override Response
    else is_injection is False
        Main->>Matcher: match_transaction(complaint, history)
        activate Matcher
        Matcher->>Matcher: normalize_text & extract entities
        Matcher->>Matcher: score candidate transactions
        Matcher->>Matcher: evaluate_consistency(complaint, tx)
        Matcher-->>Main: matched_tx, verdict, reason_codes
        deactivate Matcher

        Main->>Classifier: classify(complaint, user_type, matched_tx, verdict)
        activate Classifier
        Classifier-->>Main: case_type, severity, department, human_review
        deactivate Classifier

        Main->>Generator: generate(complaint, lang, case_type, severity, dept, verdict, tx, history)
        activate Generator
        Note over Generator: Checks GEMINI_API_KEY.<br/>Uses LLM if key present,<br/>else uses templates.
        Generator-->>Main: response_texts (summary, action, reply)
        deactivate Generator

        Main->>Safety: sanitize(response_texts, fallback_templates)
        activate Safety
        Safety->>Safety: audit_response(reply, action)
        Safety-->>Main: safe_response_texts
        deactivate Safety
    end
    
    Main-->>Client: 200 OK (TicketAnalysisResponse JSON)
    deactivate Main
```

---

## 3. Component Diagram (Software Modules)

This diagram demonstrates how application layers are segregated according to SOLID principles.

```mermaid
classDiagram
    class FastAPIApp {
        +GET /health()
        +POST /analyze_ticket()
    }
    class TicketSchemas {
        +TicketAnalysisRequest
        +TicketAnalysisResponse
        +TransactionHistoryEntry
    }
    class Config {
        +Settings settings
    }
    class TransactionMatcher {
        +match_transaction()
        +evaluate_consistency()
    }
    class CaseClassifier {
        +classify()
    }
    class ResponseGenerator {
        +generate()
        +_generate_templates()
        +_generate_llm()
    }
    class SafetyEngine {
        +detect_prompt_injection()
        +audit_response()
        +sanitize()
    }

    FastAPIApp ..> TicketSchemas : uses
    FastAPIApp ..> Config : imports
    FastAPIApp ..> TransactionMatcher : calls
    FastAPIApp ..> CaseClassifier : calls
    FastAPIApp ..> ResponseGenerator : calls
    FastAPIApp ..> SafetyEngine : calls
    TransactionMatcher ..> TicketSchemas : uses
    ResponseGenerator ..> Config : uses
    ResponseGenerator ..> TicketSchemas : uses
```

---

## 4. Deployment Diagram (Infrastructure Runtime Environment)

This diagram outlines how the service is run via Docker, exposed publicly to the judging network, and mapped to the container filesystem.

```mermaid
graph TD
    subgraph Deployed Cloud Platform (Render/Railway/Poridhi)
        InternetGateway[HTTPS Internet Gateway] -->|Exposes Port 80/443| DockerContainer[Docker Container: queuestorm-investigator]
        
        subgraph Docker Environment
            DockerContainer -->|Binds to Port 8000| Uvicorn[Uvicorn WSGI Server]
            Uvicorn -->|Runs| FastAPI[FastAPI Backend Application]
            
            subgraph Filesystem
                FastAPI -->|Reads Config| EnvVars[Environment Variables: .env]
                FastAPI -->|Executes Code| Workspace[/workspace/backend/app]
            end
        end
    end

    Client[Judge / Automated Harness] -->|Triggers Tests / Analyze requests| InternetGateway
```
