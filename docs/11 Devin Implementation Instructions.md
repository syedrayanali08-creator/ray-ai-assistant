# `/docs/11 Devin Implementation Instructions.md`

# Ray — Devin Implementation Instructions

## Role

You are the primary software engineer responsible for implementing Ray.

The project documentation inside `/docs` defines the product requirements, architecture, behavior, and goals.

Read all documentation before writing code.

Do not immediately start implementation after reading one document.

First understand:

* product goals
* architecture
* agent system
* database design
* integrations
* UI requirements

---

# Development Rules

## 1. Build Incrementally

Do not attempt to build the entire system at once.

Implement one working component at a time.

Each stage should:

* compile successfully
* be testable
* be documented
* avoid breaking previous functionality

---

## 2. Prioritize Functionality

The priority is:

1. Working Ray assistant
2. Memory
3. Agents
4. Integrations
5. Voice
6. Advanced visuals

Do not spend excessive time polishing UI before the core system works.

---

## 3. Keep Architecture Modular

Follow the documented architecture.

Avoid:

* one large AI prompt
* tightly coupled features
* duplicated logic
* hardcoded integrations

Every major capability should be its own module.

---

# Initial Tasks

Before coding:

1. Analyze the documentation.
2. Identify missing information.
3. Recommend improvements.
4. Propose the final technology choices.
5. Create an implementation plan.

Do not begin feature development until the plan is clear.

---

# Technology Requirements

Prefer:

* free tools
* open-source libraries
* free APIs
* local solutions

Do not introduce paid dependencies.

If a service requires payment:

* identify it
* suggest alternatives
* wait for approval

---

# Code Quality Requirements

Code should include:

* clear naming
* useful comments
* documentation
* error handling
* maintainable structure

Avoid:

* unnecessary complexity
* premature optimization
* unused dependencies

---

# AI System Requirements

The AI layer should support:

* multiple agents
* memory retrieval
* tool usage
* future model replacement

Do not hardcode Ray to one AI provider.

The system should allow changing models later.

---

# Agent Development

Every agent must define:

* purpose
* responsibilities
* tools
* memory access
* limitations

Agents should communicate through the Executive Agent.

---

# Integration Development

External integrations should use a common tool system.

Examples:

* GitHub
* Calendar
* Notion
* Obsidian

Do not directly connect agents to external services.

---

# Voice Development

Voice interaction is a core feature.

The system should eventually support:

* wake word activation ("Ray")
* speech-to-text
* text-to-speech

Prioritize free solutions.

---

# Debugging Approach

When problems occur:

1. Identify the root cause.
2. Explain the issue.
3. Suggest solutions.
4. Implement the fix.
5. Verify functionality.

Do not hide errors.

---

# Documentation

Update documentation when:

* architecture changes
* new agents are added
* new integrations are added
* major decisions are made

The repository should always represent the current system.

---

# Git Workflow

Use:

* clear commits
* descriptive messages
* organized branches when needed

Each major feature should be independently reviewable.

---

# Final Goal

Build Ray as a functional personal AI assistant with:

* Jarvis-inspired dashboard
* voice interaction
* wake-word activation
* persistent memory
* specialized agents
* productivity integrations
* coding assistance
* learning assistance
* research assistance

The final system should be a polished, maintainable, and impressive software project.
