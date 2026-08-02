# `/docs/14 Final Devin Task Prompt.md`

# Devin Task Prompt — Build Ray

## Project Name

Ray — Personal AI Assistant

---

# Role

You are the primary developer responsible for building Ray.

The `/docs` folder contains the complete product specification, architecture, requirements, and development plan.

These documents are the source of truth.

Read all documentation before making implementation decisions.

---

# First Action: Analyze

Before writing code:

1. Read every document inside `/docs`.
2. Understand the intended architecture.
3. Identify any conflicts or missing information.
4. Recommend improvements if necessary.
5. Create an implementation plan.

Do not immediately start coding.

The goal is to build the correct system, not just generate code quickly.

---

# Product Goal

Build Ray, a personal AI assistant inspired by Jarvis.

Ray should feel like a unified intelligent system that helps the user:

* organize life
* manage tasks
* manage calendars
* learn new concepts
* build software projects
* research ideas
* understand technology
* maintain personal knowledge

---

# Core Experience

The user should be able to:

## Communicate

Through:

* text
* voice
* eventually wake-word activation ("Ray")

---

## Ask For Help

Examples:

"Plan my week."

"Help me continue my Processing game."

"Teach me React."

"Analyze my GitHub project."

"Help me learn databases."

"Research this idea."

---

## Receive Intelligent Assistance

Ray should:

* understand context
* retrieve memory
* choose appropriate agents
* use tools
* explain actions

---

# Required Architecture

Follow the documented architecture.

Core systems:

## Frontend

Responsible for:

* dashboard
* chat interface
* Jarvis-style UI
* project views
* task views
* memory views

---

## Backend

Responsible for:

* API handling
* agent coordination
* memory retrieval
* integrations
* database operations

---

## Executive Agent

Responsible for:

* understanding requests
* coordinating agents
* combining results

---

## Specialized Agents

Implement modular agents **as code modules** (ADR-0005):

* Planning Agent
* Coding Agent
* Learning Agent
* Research Agent

Memory is a **service** called on every request, not an agent — routing it through an
LLM turn would add latency and non-determinism to the hot path. It is additionally
exposed to agents as a tool (ADR-0005).

---

# Development Approach

Build incrementally.

The canonical phase order lives in **`docs/10 Development Roadmap`**. The list
previously duplicated here has been removed because it conflicted with `docs/10`
(notably by placing the database after AI conversation, which is impossible —
conversations must be persisted).

All resolved technical decisions live in **`docs/adr/`** and are binding.

---

# Technology Requirements

Prioritize:

* free tools
* open-source libraries
* free APIs
* local solutions

Do not introduce paid dependencies unless absolutely required.

If a paid service appears necessary:

1. Explain why.
2. Provide free alternatives.
3. Wait for approval.

---

# Coding Requirements

Code should be:

* modular
* documented
* maintainable
* readable
* properly structured

Avoid:

* unnecessary complexity
* temporary hacks becoming permanent
* tightly coupled systems

---

# Learning Requirement

Ray is also a learning platform.

The system should be understandable.

When implementing:

Explain:

* why a technology was chosen
* how components work
* what design decisions were made

The user should learn software engineering concepts through building Ray.

---

# Integration Requirements

Ray should eventually connect with:

* calendar
* Notion
* Obsidian
* GitHub
* local files

Use a modular tool system.

Do not directly hardcode integrations into agents.

---

# UI Requirements

The interface should be visually impressive.

Design goals:

* Jarvis-inspired dashboard
* futuristic AI assistant feel
* smooth interactions
* clean information display

Prioritize usability over unnecessary effects.

---

# Voice Requirements

Ray is **voice-first** (ADR-0009). Wake-word activation using "Ray" is a core identity
feature, not a future enhancement.

The architecture must support the full pipeline from Phase 1 — microphone → wake word →
speech-to-text → AI → text-to-speech — while the implementation improves
incrementally: browser fallbacks in Phase 2, local faster-whisper and Piper in Phase 6,
openWakeWord activation in Phase 6b.

All chosen voice components are free and run locally.

---

# Repository Requirements

Create:

* clean folder structure
* README
* setup instructions
* environment documentation
* contribution/development notes

The repository should be presentable as a professional software project.

---

# Working Style

When making progress:

Report:

* what was completed
* what changed
* what remains
* any decisions made

If blocked:

Explain:

* the issue
* possible solutions
* recommended approach

Do not silently make major architectural changes.

---

# Final Goal

Create a working personal AI assistant that feels like a real-world Jarvis system:

* intelligent
* personalized
* extensible
* visually impressive
* useful daily

The first version should prioritize a complete working foundation that can continue evolving.
