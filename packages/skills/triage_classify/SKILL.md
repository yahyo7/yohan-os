---
name: triage_classify
description: Classify an unread email into needs_reply, fyi, or spam
model_role: classifier
---
Classify this email into exactly one label: needs_reply, fyi, or spam.

- needs_reply: a person is asking you something or expects a response.
- fyi: informational, no response expected.
- spam: promotional, automated, or unsolicited bulk mail.

From: {sender}
Subject: {subject}
Snippet: {snippet}

Answer with only the label.
