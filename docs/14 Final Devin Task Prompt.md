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

Implement modular agents:

* Planning Agent
* Coding Agent
* Learning Agent
* Research Agent
* Memory Agent

---

# Development Approach

Build incrementally.

Recommended order:

1. Project foundation
2. Frontend/backend connection
3. AI conversation
4. Database
5. Memory
6. Agent system
7. Tasks/projects
8. Integrations
9. Voice
10. UI improvements

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

Ray should eventually support:

* speech-to-text
* text-to-speech
* wake word activation using "Ray"

Use free solutions where possible.

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
