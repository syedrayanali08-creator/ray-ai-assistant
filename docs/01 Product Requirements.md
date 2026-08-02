# `/docs/01 Product Requirements.md`

# Ray — Product Requirements Document (PRD)

## Document Purpose

This document defines the functional requirements for Ray's first complete version.

Ray is a personal AI assistant inspired by Jarvis-style systems. The goal is to create a free, fully functional AI companion capable of assisting with organization, learning, coding, research, and personal projects.

---

# Product Constraints

## Cost Requirements

Ray must be built using free tools, free APIs, and free services wherever possible.

The project must not require paid subscriptions or recurring costs after development.

The only paid tool assumed is the existing Devin subscription provided to the creator.

Preferred solutions:

* open-source software
* free API tiers
* local models where practical
* free hosting tiers
* free databases
* self-hosted services

Any dependency requiring payment must be clearly identified and avoided unless there is no reasonable alternative.

---

# Target User

Ray Version 1 is designed for a single user: its creator.

The system should optimize for deep personalization rather than generic multi-user functionality.

The architecture should remain clean enough that future expansion is possible.

---

# Core User Flows

## 1. General Conversation

User can communicate with Ray through:

* text input
* voice input
* voice output

Example:

User:

> "Help me plan tomorrow."

Ray:

* checks calendar
* checks tasks
* checks priorities
* creates a schedule
* explains recommendations

---

# 2. Task Management

Ray should allow users to:

* create tasks
* edit tasks
* delete tasks
* prioritize tasks
* assign deadlines
* categorize tasks
* track completion

Example:

User:

> "I need to finish my Processing game before university starts."

Ray should:

* create a project
* break it into tasks
* assign priorities
* track progress

---

# 3. Calendar Management

Ray should support:

* viewing schedule
* creating events
* editing events
* reminders
* time blocking
* planning sessions

Example:

User:

> "Schedule two hours for coding tomorrow evening."

Ray should create the appropriate event.

---

# 4. Project Management

Ray should maintain active projects.

Each project should contain:

* title
* description
* goals
* roadmap
* tasks
* status
* notes
* related resources

Examples:

* Ray development
* Processing games
* university preparation
* hackathon projects

---

# 5. Coding Assistant

Ray should act as a coding mentor.

Required capabilities:

* understand project context
* explain concepts
* review code
* debug errors
* suggest next steps
* create learning paths

The assistant should adapt explanations based on the user's current skill level.

Example:

User:

> "What should I implement next in my Processing game?"

Ray should know previous progress and provide guidance.

---

# 6. Learning Assistant

Ray should help users learn.

Capabilities:

* explain concepts
* generate practice problems
* create study plans
* quiz users
* track learning progress

Examples:

* Waterloo CS courses
* programming
* mathematics
* technical skills

---

# 7. Research Assistant

Ray should help investigate ideas.

Required capabilities:

* summarize information
* organize notes
* create research plans
* compare technologies
* suggest learning paths

Example:

User:

> "How could I realistically build Spider-Man-style technology?"

Ray should create structured research areas and learning steps.

---

# 8. Memory System

Ray must maintain persistent memory.

Memory categories:

## User Memory

Stores:

* preferences
* communication style
* goals
* interests

---

## Project Memory

Stores:

* project details
* decisions
* progress
* previous discussions

---

## Learning Memory

Stores:

* learned concepts
* weaknesses
* completed topics

---

## Conversation Memory

Stores:

* important previous conversations
* relevant context

---

# Dashboard Requirements

The main interface should resemble a futuristic AI assistant dashboard.

Required components:

## Main Conversation Area

* text chat
* voice interaction
* AI responses

---

## Current Context Panel

Displays:

* active project
* current goals
* recent memories
* active tasks

---

## Task Panel

Displays:

* upcoming tasks
* priorities
* deadlines

---

## Calendar Panel

Displays:

* upcoming events
* schedule

---

## Agent Status Panel

Displays:

* active agent
* tools being used
* current operations

---

# Voice Requirements

Ray should support:

## Speech Input

User can speak commands naturally.

Examples:

* "Add this to my calendar."
* "Help me debug this."
* "Plan my week."

---

## Speech Output

Ray should be able to respond verbally.

Voice interaction should feel conversational.

---

# Technical Requirements

## Modularity

The system must support adding new agents without rewriting existing functionality.

---

## Free Technology Requirement

Preferred technologies should prioritize:

* open-source frameworks
* free APIs
* local execution
* free-tier services

---

## Security

The system must:

* protect personal data
* avoid exposing private information
* store credentials securely
* allow user control over stored memory

---

# MVP Completion Criteria

Ray Version 1 is complete when:

* user can communicate with Ray through text
* user can communicate through voice
* Ray has persistent memory
* Ray can manage tasks
* Ray can manage calendar events
* Ray can track projects
* Ray has specialized agents
* Ray provides coding guidance
* Ray provides learning assistance
* Ray provides research assistance
* Ray has a Jarvis-style dashboard
* the system runs without requiring paid services

---

# Development Priority Order

1. Project foundation
2. User interface
3. AI conversation system
4. Memory system
5. Agent architecture
6. Task management
7. Calendar integration
8. Coding assistant
9. Learning assistant
10. Research assistant
11. Voice interaction
12. Dashboard improvements

---

# Out of Scope for Initial Release

Do not prioritize:

* mobile application
* public users
* payments
* social features
* enterprise features
* unnecessary animations
* advanced automation before core functionality works

The priority is creating a reliable personal AI assistant first.
