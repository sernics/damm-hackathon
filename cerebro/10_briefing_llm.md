# AI Driver Briefing System

### Turning Logistics Data into Actionable Route Intelligence

## Overview

This project aims to build an AI-powered operational assistant for delivery drivers.

The system takes structured delivery data (orders, products, route information, vehicle capacity, customer notes, historical tips, etc.) and transforms it into a clear, human-style daily briefing for the assigned driver.

Instead of reading raw ERP exports, spreadsheets, or internal notes, drivers receive a practical route summary written as if it came from an experienced senior colleague.

---

## The Core Problem

In many logistics companies, the most valuable operational knowledge is not stored in systems.

It lives in the minds of experienced drivers.

They know things like:

- Which customers open late  
- Where parking is difficult  
- Which entrance to use  
- Which deliveries must go first  
- Which customers return many empties  
- How to unload faster  
- Where police usually check double parking  
- Which pallets must stay accessible in the truck  
- What order of stops saves the most time

When an experienced driver is absent, replacements lose efficiency immediately.

This creates:

- Delays  
- Failed deliveries  
- Poor customer experience  
- Stress for new drivers  
- Loss of “tribal knowledge”

---

## Proposed Solution

Build an **AI Driver Briefing Generator**.

The system ingests multiple data sources and produces a single operational briefing.

---

## Input Sources

### 1. Structured Order File

Example:

{
  "order_date": "2026-01-30",
  "client_name": "AKI MISMO",
  "total_lines": 74,
  "total_quantity": 231,
  "transport_ids": ["11420415"],
  "ordered_items": [
    {
      "material": "ED13",
      "description": "ED13",
      "quantity": 4.0,
      "unit": "CAJ"
    }
  ]
}

---

### 2. Route Metadata (Optional)

- Route code  
- Number of stops  
- Total volume (boxes, pallets, barrels)  
- Departure time  
- Estimated return time  
- Vehicle type  
- Capacity constraints  
- Geographic clusters

---

### 3. Knowledge Base (Tips Markdown File)

Human-written operational knowledge:

- Arrive before 09:00, street gets crowded later  
- Use side entrance for faster unloading  
- Customer prefers cold drinks first  
- Leave space for empty returns  
- Manager signs quickly if products are pre-separated  
- Avoid double parking near police hours

---

### 4. Optional Historical Data

- Previous delivery issues  
- Average unloading time per client  
- Driver feedback notes  
- Delay patterns  
- Common exceptions

---

## AI Output

The system generates a **human-like driver briefing**.

Example output:

AKI MISMO - 30 January 2026

Today you have a large mixed delivery: 74 lines and 231 units.

Best approach: arrive before 09:00. The street gets congested later and parking becomes difficult. If needed, park at the corner and use a pallet jack.

Prioritize separating UE050 and UE902 — they are usually requested immediately by the client.

Unload strategy:

- Cold products first  
- Large boxes to warehouse area  
- Small mixed items to bar counter

Expect a high number of empty returns. Make sure to leave space in the truck before starting delivery.

If Sergio is present, he signs quickly if everything is well organized.

Avoid arriving between 13:30 and 14:30 due to peak activity.

Veteran tip: keep urgent items near the truck door to avoid multiple re-entries.  

Note: This output needs to be in Spanish. It should also be able to output in Catalan.

---

## Key Value Proposition

### For Drivers

- Faster understanding of route  
- Less cognitive load  
- Practical real-world instructions  
- Reduced mistakes  
- Better time management

---

### For Operations

- Captures expert knowledge  
- Reduces dependency on specific drivers  
- Improves consistency  
- Faster onboarding of new drivers  
- Fewer delivery failures

---

### For Business

- Increased delivery efficiency  
- Better customer satisfaction  
- Lower operational cost  
- Standardized execution across fleet

---

## Technical Architecture

### Backend

- Python  
- FastAPI

---

### LLM Layer

- Anthropic API

---

### Data Processing

- JSON ingestion  
- Markdown parsing  
- Context merging , we need to match precisely the client names in the JSON and the Markdown
- Prompt orchestration

---

### Frontend

- Web dashboard  
- Delivery of the briefing should be made to the delivery note ("albaran")

---

## Prompt Strategy

System prompt concept:

You are a veteran logistics driver with 25+ years of experience.

Your job is to convert structured delivery data into a practical, human, operational briefing for a replacement driver.

Be concise, direct, and realistic.

Focus on:

- Route optimization
- Customer behavior
- Parking constraints
- Loading/unloading strategy
- Timing risks
- Operational tips

Write as a senior colleague speaking to another driver.

---

## Why This Works

Most logistics companies already have data.

They lack interpreted operational intelligence.

This system converts:

raw data → human expertise

