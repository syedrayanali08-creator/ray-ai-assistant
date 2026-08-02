# `/docs/09 UI and UX Specification.md`

# Ray — UI and UX Specification

## Purpose

This document defines the user interface and experience requirements for Ray.

Ray should feel like a personal AI assistant, not a traditional productivity application.

The interface should combine:

* AI conversation
* personal dashboard
* project management
* memory visibility
* task organization
* futuristic Jarvis-inspired design

---

# Design Goal

The user should feel like they are interacting with an intelligent system.

The interface should communicate:

* awareness
* organization
* intelligence
* personalization

The design should be visually impressive while remaining practical and fast.

---

# Overall Layout

The primary dashboard should contain several connected areas.

High-level structure:

```
-------------------------------------------------
| Ray Status | User Context | System Information |
-------------------------------------------------
|                                               |
|              Main Conversation                |
|                                               |
-------------------------------------------------
| Tasks | Projects | Calendar | Memory | Agents |
-------------------------------------------------
```

---

# Main Dashboard

The dashboard is the primary screen.

It should display:

## Conversation Area

The central interaction point.

Features:

* text chat
* voice controls
* conversation history
* streaming responses
* markdown support
* code formatting

---

## Ray Status Area

Displays:

* current activity
* active agent
* current task
* system state

Examples:

```
Ray is analyzing your GitHub repository.

Active Agent:
Coding Agent

Using:
Project Memory
GitHub Integration
```

---

## Personal Overview Area

Displays:

* today's priorities
* upcoming events
* active projects
* important reminders

Example:

```
Today's Focus

1. Complete enemy AI system
2. Review Waterloo preparation tasks
3. Gym at 7 PM
```

---

# Jarvis-Inspired Visual Design

The interface should take inspiration from AI assistant interfaces.

Important characteristics:

## Futuristic Feel

Use:

* clean dark interface
* glowing elements
* smooth transitions
* subtle animations
* system-style panels
* data visualization

Avoid:

* excessive decoration
* distracting animations
* difficult navigation

---

# Voice Interface

**Voice is a primary interaction method, not a secondary one (ADR-0009).** The target
experience is: the user says "Ray", Ray activates, the user speaks, Ray answers aloud.
The interface is designed around that from the start, even while the underlying voice
implementation is still improving.

The interface should include:

## Voice Button

Allows:

* start listening
* stop listening
* indicate processing

---

## Voice State Indicators

Examples:

```
Idle (wake word armed)

Listening...

Processing...

Responding...
```

When wake-word detection is armed the interface must show a persistent, unmistakable
microphone indicator, and turning it off must always be one click away (`docs/12`).

---

# Agent Visualization

Ray should make its internal systems understandable.

Display:

* current agent
* tools being used
* completed actions

Example:

```
Executive Agent

↓

Coding Agent

↓

GitHub Tool

↓

Project Analysis Complete
```

This makes Ray feel intelligent while remaining transparent.

---

# Project View

Each project should have its own dashboard.

Example:

## Processing Game

Display:

```
Project Status

Progress: 65%

Current Goal:
Implement mouse aiming

Completed:
✓ Player movement
✓ Enemy spawning

Next:
Collision system
```

---

# Memory View

Users should be able to see and manage memories.

Features:

* search memories
* view categories
* edit memories
* delete memories

Example:

```
Memory

Category:
Coding Preference

Content:
User prefers explanations before code.

Used By:
Coding Agent
Learning Agent
```

---

# Task View

Features:

* create tasks
* organize priorities
* mark completion
* connect tasks to projects

Example:

```
Ray Project

High Priority

Implement memory database

Due:
August 15
```

---

# Calendar View

Features:

* daily schedule
* weekly schedule
* upcoming events
* time blocks

Should integrate with external calendars where possible.

---

# Learning View

Displays:

* current topics
* progress
* recommended next steps

Example:

```
Learning Path

React

██████░░░░ 60%

Next:
State Management
```

---

# Responsive Design

The interface should work on:

* desktop first
* tablet
* mobile in future versions

Stack: Next.js 15 + React 19 + TypeScript, Tailwind CSS v4, shadcn/ui primitives,
TanStack Query, and Framer Motion used sparingly (ADR-0011). Streaming is consumed from
the SSE chat endpoint (ADR-0007).

The first version should prioritize desktop because development and usage will primarily occur there.

---

# Frontend Requirements

Preferred technologies:

* React
* Next.js
* TypeScript

Reason:

* strong ecosystem
* suitable for dynamic interfaces
* commonly used professionally

---

# UI Component Requirements

Components should be reusable.

Examples:

* ChatPanel
* TaskPanel
* CalendarPanel
* AgentStatus
* AgentTrace — renders the executive → agent → tool chain for a response
* ApprovalCard — shows the exact payload of a side-effecting tool call with
  Approve / Reject, and an "always allow" option where permitted (ADR-0014)
* MemoryCard — including provenance ("why does Ray believe this?")
* ProjectCard
* VoiceControl — wake-word state, listening state, push-to-talk fallback

Avoid creating duplicate UI logic.

---

# User Experience Rules

Ray should:

* provide clear feedback
* explain actions
* avoid silent failures
* keep important information visible
* minimize unnecessary clicks

---

# Future UI Improvements

Possible additions:

* holographic-style visualizations
* customizable dashboard layouts
* desktop application
* mobile application
* custom themes
* animated AI avatar

---

# Completion Criteria

The UI system is complete when:

* user can interact with Ray through the dashboard
* text conversations work
* voice interaction works
* tasks/projects/calendar are visible
* memory is accessible
* agents and actions are understandable
* interface has a polished Jarvis-inspired appearance
