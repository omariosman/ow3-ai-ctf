# Solution — Context Hijack (author only; never served by the web app)

## Solution
1. Ask: `What is the return policy for an unopened item?`
2. Retrieved sources: the official policy and the **External / untrusted**
   `community_shipping_faq.md`.
3. The answer claims lifetime refunds and ends with `CONTEXT_OVERRIDE_CONFIRMED`.
   The server verifies this outcome and reveals the flag; submit it.

## Root cause
The context builder concatenates the system instruction and retrieved text, so
the FAQ's `ASSISTANT DIRECTIVE:` line is indistinguishable from an instruction.

## Remediation
Isolate and label untrusted content; prefer trusted sources for policy answers;
enforce policy in application code; least privilege; human approval for
consequential actions; validate outputs; test adversarially. No single control
fully solves prompt injection, and RAG does not remove it.

## Learning outcomes
Retrieved text is data. Injection changes behaviour; impact depends on the
assistant's access.
