# `/docs/06 Database and Data Model.md`

# Ray — Database and Data Model

## Purpose

This document defines how Ray stores and organizes information.

The database should support:

* user memory
* conversations
* projects
* tasks
* calendar events
* agents
* integrations
* learning progress

The design should remain flexible as Ray gains more capabilities.

---

# Database Requirements

The database must be:

* free to use
* open-source or free-tier compatible
* reliable
* scalable
* easy to maintain

Preferred database:

## PostgreSQL

Reasons:

* open-source
* widely used
* supports structured data
* supports vector search extensions
* strong ecosystem

---

# Core Data Model

High-level relationship:

```
User

 |
 +--- Memories
 |
 +--- Projects
 |
 +--- Tasks
 |
 +--- Calendar Events
 |
 +--- Conversations
 |
 +--- Learning Records
 |
 +--- Integrations
 |
 +--- Agent Activity
```

---

# Tables

## 1. User

Stores user profile information.

Example fields:

```
User
- id
- name
- email
- created_at
- preferences
- settings
```

Purpose:

Stores identity and system preferences.

---

# 2. Memory

Stores long-term Ray knowledge.

Fields:

```
Memory
- id
- user_id
- category
- content
- importance
- created_at
- updated_at
- source
- embedding
```

Categories:

* user
* project
* learning
* goal
* preference
* conversation

---

# Memory Example

```
Category:
Project

Content:
User is building a Processing Java game.

Importance:
High

Source:
Conversation
```

---

# 3. Project

Stores user projects.

Examples:

* Ray
* Processing Game
* Hackathon Projects

Fields:

```
Project
- id
- user_id
- name
- description
- status
- technology_stack
- created_at
- updated_at
```

---

# 4. Project Task

Stores tasks related to projects.

Fields:

```
ProjectTask
- id
- project_id
- title
- description
- priority
- status
- deadline
- created_at
```

Example:

```
Project:
Ray

Task:
Implement voice input

Priority:
High

Status:
Pending
```

---

# 5. General Task

Stores normal life tasks.

Examples:

* homework
* reminders
* errands

Fields:

```
Task
- id
- user_id
- title
- description
- priority
- category
- status
- due_date
- created_at
```

---

# 6. Calendar Event

Stores scheduled events.

Fields:

```
CalendarEvent
- id
- user_id
- title
- description
- start_time
- end_time
- location
- source
```

Source examples:

* Ray
* Google Calendar
* Notion

---

# 7. Conversation

Stores conversations.

Fields:

```
Conversation
- id
- user_id
- title
- created_at
- updated_at
```

---

# 8. Message

Stores individual messages.

Fields:

```
Message
- id
- conversation_id
- role
- content
- timestamp
```

Roles:

* user
* assistant
* system
* agent

---

# 9. Learning Record

Stores educational progress.

Fields:

```
LearningRecord
- id
- user_id
- topic
- category
- proficiency
- notes
- last_reviewed
```

Example:

```
Topic:
Python Classes

Proficiency:
Beginner

Notes:
Understands objects but needs practice.
```

---

# 10. Agent

Stores available Ray agents.

Fields:

```
Agent
- id
- name
- description
- enabled
- configuration
```

Examples:

```
Coding Agent

Learning Agent

Planning Agent
```

---

# 11. Agent Activity

Tracks agent actions.

Fields:

```
AgentActivity
- id
- agent_id
- action
- timestamp
- result
```

Purpose:

Allows Ray to explain what happened.

Example:

```
Coding Agent

Analyzed repository

Found:
3 possible next tasks
```

---

# 12. Integration

Stores connected services.

Fields:

```
Integration
- id
- user_id
- type
- provider
- credentials_reference
- status
```

Examples:

* GitHub
* Notion
* Calendar

---

# Data Relationships

## User → Projects

One user can have many projects.

---

## Project → Tasks

One project can contain many tasks.

---

## User → Memories

One user can have many memories.

---

## Conversation → Messages

One conversation contains many messages.

---

## Agent → Activity

One agent can create many activity records.

---

# Data Storage Rules

## Do:

* store useful information
* maintain relationships
* allow searching
* track changes

## Avoid:

* storing every message permanently
* duplicate information
* unnecessary personal data

---

# Future Database Expansion

Possible additions:

* knowledge graph
* document storage
* file metadata
* user analytics
* automation workflows
* AI-generated summaries

---

# Completion Criteria

The database system is complete when:

* Ray can store user information
* Ray can remember projects
* Ray can track tasks
* Ray can store conversations
* Ray can retrieve relevant context
* Ray can connect external tools
* the design can support additional agents
