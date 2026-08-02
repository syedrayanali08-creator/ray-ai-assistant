# `/docs/05 Memory System.md`

# Ray — Memory System Specification

## Purpose

Memory is one of Ray's core capabilities.

Without memory, Ray is only a temporary chatbot.

With memory, Ray becomes a personalized assistant that understands the user's projects, goals, preferences, and history over time.

The memory system allows Ray to provide context-aware responses and improve usefulness through continued interaction.

---

# Memory Goals

Ray's memory system should:

* remember important user information
* understand ongoing projects
* track learning progress
* recall previous decisions
* avoid repeating questions
* provide relevant context automatically

---

# Memory Principles

## 1. Useful Over Complete

Ray should not store every conversation.

Memory should contain information that improves future interactions.

Examples of useful memories:

* "User prefers learning through explanations before receiving code."
* "User is building a Processing game called Starfall Sprint."
* "User is starting Waterloo CS + BBA."

Examples of unnecessary memories:

* temporary conversation details
* random one-time questions
* irrelevant messages

---

## 2. User Control

The user must be able to:

* view stored memories
* edit memories
* delete memories
* disable memory categories

Ray should never permanently store sensitive information without appropriate user control.

---

## 3. Context Awareness

Ray should automatically retrieve relevant memories.

Example:

User:

> "What should I implement next?"

Ray should recognize the active project and retrieve:

* current project state
* previous progress
* unfinished tasks
* technical decisions

---

# Memory Categories

## 1. User Profile Memory

Stores long-term information about the user.

Examples:

* preferences
* goals
* interests
* learning style
* preferred communication style

---

## 2. Project Memory

Stores information about projects.

Examples:

```
Project:
Starfall Sprint

Technology:
Processing Java

Current Status:
Player movement complete

Next Goal:
Mouse aiming system

Important Decisions:
Use classes for entities
```

---

Project memory should track:

* project description
* goals
* roadmap
* technologies
* files
* progress
* decisions
* problems
* solutions

---

## 3. Learning Memory

Stores educational progress.

Examples:

```
Topic:
Object-Oriented Programming

Status:
Intermediate

Strength:
Classes and objects

Weakness:
Inheritance
```

---

Learning memory should allow Ray to:

* avoid reteaching mastered concepts
* focus on weaknesses
* create personalized learning plans

---

## 4. Goal Memory

Stores long-term objectives.

Examples:

* university goals
* career goals
* personal projects
* skill development

Ray should use goals when recommending actions.

---

## 5. Conversation Memory

Stores important previous discussions.

Examples:

* decisions made
* plans created
* unresolved problems

Temporary conversations should not automatically become permanent memories.

---

# Memory Architecture

Memory should use multiple layers.

```id="4x5qpn"
Conversation Context

(short term)

        ↓

Working Memory

(current tasks)

        ↓

Long-Term Memory

(user knowledge)

        ↓

Knowledge Base

(projects, notes, documents)
```

---

# Short-Term Memory

Purpose:

Maintain current conversation understanding.

Stores:

* recent messages
* current request
* current reasoning context

Lifetime:

Temporary.

---

# Working Memory

Purpose:

Handle active situations.

Examples:

* current coding session
* current planning task
* active research question

Lifetime:

Hours to days.

---

# Long-Term Memory

Purpose:

Permanent useful information.

Stores:

* preferences
* projects
* goals
* learned information

Lifetime:

Months to years.

---

# Memory Retrieval

When responding, Ray should:

1. Understand the user's request.
2. Identify relevant topics.
3. Search memory.
4. Retrieve useful context.
5. Include context in reasoning.
6. Generate response.

Example:

User:

> "Help me continue my game."

Ray should retrieve:

* game name
* previous progress
* code context
* current objective

---

# Memory Storage Process

When Ray detects potentially useful information:

1. Identify information type.
2. Determine importance.
3. Check for duplicates.
4. Store if valuable.
5. Allow future retrieval.

---

# Memory Database Requirements

The system should prioritize free technologies.

Preferred approach:

## Primary Storage

Relational database:

* PostgreSQL

Stores:

* users
* projects
* tasks
* memories
* conversations

---

## Semantic Search

Used for finding related memories.

Preferred options:

* PostgreSQL vector extension
* local vector databases
* open-source embeddings

Avoid paid memory services.

---

# Memory Security

Ray must:

* protect stored information
* avoid unnecessary collection
* allow deletion
* keep credentials secure

Personal information belongs to the user.

---

# Memory Interface

Ray should eventually provide a memory dashboard.

Features:

* view memories
* search memories
* edit memories
* remove memories
* see why a memory exists

Example:

```
Memory:

"User prefers learning through guidance first."

Created:
August 2026

Used for:
Coding Agent
Learning Agent
```

---

# Future Memory Improvements

Possible additions:

* automatic knowledge graph
* relationship mapping
* document understanding
* personalized recommendations
* memory importance scoring
* automatic project summaries

---

# Completion Criteria

The memory system is complete when:

* Ray remembers important user information
* Ray retrieves relevant context automatically
* Ray understands active projects
* Ray improves conversations over time
* users can control stored information
* memory works without paid services
