# Assessment Model

This document describes the core domain model for Socratic's assessment system.

## Overview

Socratic is an AI-mediated oral assessment system. Instructors define learning objectives, assign them to learners, and the system conducts conversational assessments to evaluate learner understanding.

## Core Entities

### Organization

The top-level tenant. All users, objectives, and assignments belong to an organization.

### User

Users have roles within organizations via memberships:

- **Instructor**: Creates objectives, assigns assessments, reviews results
- **Learner**: Completes assigned assessments

A user can have different roles in different organizations.

### Objective

An objective defines what a learner should demonstrate understanding of. Created by instructors.

| Field                      | Description                                       |
| -------------------------- | ------------------------------------------------- |
| `title`                    | Short name for the objective                      |
| `description`              | Detailed explanation of what mastery looks like   |
| `scope_boundaries`         | What is explicitly out of scope                   |
| `time_expectation_minutes` | Expected assessment duration                      |
| `initial_prompts`          | Opening questions to start the conversation       |
| `challenge_prompts`        | Follow-up questions to probe deeper understanding |
| `extension_policy`         | Whether to explore beyond the defined scope       |
| `status`                   | Draft, Published, or Archived                     |

### Rubric Criterion

Each objective has rubric criteria that define how to evaluate learner responses.

| Field                 | Description                                       |
| --------------------- | ------------------------------------------------- |
| `name`                | Criterion name (e.g., "Conceptual Understanding") |
| `description`         | What this criterion measures                      |
| `evidence_indicators` | Observable signs of competence                    |
| `failure_modes`       | Common misconceptions or errors                   |
| `grade_thresholds`    | What constitutes each grade level                 |
| `weight`              | Relative importance in overall grade              |

### Assignment

Links an objective to a specific learner. Created by instructors.

| Field             | Description                           |
| ----------------- | ------------------------------------- |
| `objective_id`    | What to assess                        |
| `assigned_by`     | Instructor who created the assignment |
| `assigned_to`     | Learner who must complete it          |
| `available_from`  | When the assignment becomes available |
| `available_until` | Deadline for completion               |
| `max_attempts`    | How many tries the learner gets       |
| `retake_policy`   | Rules for additional attempts         |

### Assessment Attempt

A single instance of a learner taking an assessment.

| Field              | Description                          |
| ------------------ | ------------------------------------ |
| `assignment_id`    | Which assignment this attempt is for |
| `learner_id`       | Who is taking the assessment         |
| `status`           | Current state (see lifecycle below)  |
| `started_at`       | When the conversation began          |
| `completed_at`     | When the conversation ended          |
| `grade`            | AI-assigned grade (S/A/C/F)          |
| `confidence_score` | AI's confidence in the grade         |

## Attempt Lifecycle

```
NotStarted → InProgress → Completed → Evaluated → Reviewed
```

1. **NotStarted**: Assignment exists but learner hasn't begun
2. **InProgress**: Learner is actively in conversation with AI
3. **Completed**: Conversation finished, awaiting AI evaluation
4. **Evaluated**: AI has assigned a grade and confidence score
5. **Reviewed**: Instructor has reviewed and optionally overridden the grade

## Grading Scale

| Grade | Meaning                                                  |
| ----- | -------------------------------------------------------- |
| S     | Satisfactory - Demonstrates clear mastery                |
| A     | Acceptable - Meets expectations with minor gaps          |
| C     | Conditional - Partial understanding, needs reinforcement |
| F     | Fail - Does not demonstrate required understanding       |

## Strands (Optional)

Strands group objectives into learning progressions with dependencies.

- **Strand**: Named collection of objectives (e.g., "Algebra Fundamentals")
- **ObjectiveInStrand**: Places an objective at a position within a strand
- **ObjectiveDependency**: Defines prerequisite relationships between objectives
  - **Hard**: Must complete prerequisite before attempting
  - **Soft**: Recommended but not required

## Typical Workflow

### Instructor Flow

1. Create an **Objective** with description and prompts
2. Add **Rubric Criteria** to define evaluation standards
3. Create **Assignments** linking objectives to learners
4. Review completed attempts and accept or override grades

### Learner Flow

1. View available **Assignments** on dashboard
2. Start an **Attempt** for an assignment
3. Complete the AI-mediated conversation
4. View results after instructor review

## Entity Relationships

```
Organization
    ├── Users (via Memberships)
    ├── Objectives
    │       └── RubricCriteria
    ├── Assignments
    │       └── AssessmentAttempts
    └── Strands
            └── ObjectivesInStrand
                    └── ObjectiveDependencies
```

## API Endpoints

### Objectives

- `POST /api/objectives` - Create objective
- `GET /api/objectives/{id}` - Get objective details
- `GET /api/objectives/{id}/criteria` - Get rubric criteria

### Assignments

- `POST /api/assignments` - Create single assignment
- `POST /api/assignments/bulk` - Create multiple assignments
- `GET /api/assignments/{id}` - Get assignment details

### Assessments

- `POST /api/assessments/{assignment_id}/start` - Begin attempt
- `POST /api/assessments/{attempt_id}/message` - Send message in conversation
- `POST /api/assessments/{attempt_id}/complete` - End conversation
- `POST /api/assessments/{attempt_id}/evaluate` - Trigger AI evaluation

### Reviews (Instructor)

- `GET /api/reviews` - List pending reviews
- `GET /api/reviews/{attempt_id}` - Get review details
- `POST /api/reviews/{attempt_id}/accept` - Accept AI grade
- `POST /api/reviews/{attempt_id}/override` - Override with different grade
