---
name: venue-lost-item-recovery-kit
description: Organize fast, safe outreach to cafes, gyms, taxis, hotels, and venues after a lost item, with contact tracking and ownership verification templates.
version: "1.0.0"
type: prompt-flow
tags:
  - lost-item
  - urgent-admin
  - venue-outreach
  - travel-logistics
  - personal-organization
author: Bell (design)
---

# Venue Lost Item Recovery Kit

## Overview

Venue Lost Item Recovery Kit helps users act quickly after leaving an item at a cafe, gym, taxi, hotel, event space, restaurant, rideshare, public venue, or similar location. It turns panic into a short recovery sequence: capture item facts, list likely locations, draft messages, track responses, and plan safe pickup proof.

This skill is distinct from lost-wallet, stolen-item, package-claim, and insurance-claim workflows. It focuses on ordinary lost property outreach and safe ownership verification. If the lost item includes payment cards, government ID, passport, keys with address details, medication, or high-risk personal data, route the user to appropriate urgent protective steps in addition to venue outreach.

## When to Use

Use this skill when the user says they lost or left something at:

- Cafe, bar, restaurant, club, theater, gym, salon, clinic, coworking space, school, library, hotel, taxi, rideshare, bus, train station, airport lounge, conference, or event venue
- A recent route with multiple possible stops
- A place where staff may keep a lost-and-found log

**Trigger phrases:** "I left something at a cafe", "Lost item at hotel", "I forgot my bag in a taxi", "Message a venue about lost property", "How do I recover my lost item", "Lost and found contact template"

## Required Inputs

Ask for enough facts to make outreach specific without exposing sensitive details:

- Item type and general description
- Last known time and place
- Likely route or sequence of stops
- Distinctive but safe identifiers, such as color, brand, case, sticker, initials, or non-sensitive contents
- Contact channels already available: phone, email, website form, app support, receipt, booking reference
- Whether the item contains urgent sensitive contents

Avoid asking the user to share full serial numbers, full ID numbers, complete card numbers, home address, lock codes, passwords, or other sensitive identifiers in messages.

## Workflow

### Step 1 - Stabilize and Triage Urgency

Start with a calm, action-oriented response. Identify whether the item creates immediate risk:

- Payment cards, passport, government ID, keys with address, work badge, medication, laptop, phone, or confidential documents
- If urgent risk exists, advise protective action through the appropriate provider or authority while continuing recovery outreach
- If the item is ordinary, proceed directly to outreach planning

Do not overstate risk. Keep the user focused on the next contact.

### Step 2 - Build the Item Fact Card

Create a concise fact card:

- Item type
- General description
- Safe identifiers
- Last seen location and time
- Route or seat/table/room details
- Possible staff interaction or receipt reference
- Preferred contact method
- Pickup availability

Mark sensitive details as "do not include in first message" unless staff specifically need them later for verification.

### Step 3 - Rank Likely Locations

Help the user list and prioritize places to contact:

1. Last confirmed location
2. Places where the item may have been moved by staff
3. Transportation provider, taxi company, rideshare app, or hotel front desk
4. Nearby stops on the route
5. Central lost-and-found desk for malls, campuses, transit systems, airports, conferences, or venues

For each location, note best channel, hours, reference number, and follow-up timing.

### Step 4 - Draft Outreach Messages

Provide concise templates adapted to the location type.

Include:

- Polite opening
- Date, approximate time, and area
- General item description
- Safe distinguishing detail
- Request to check lost and found
- Contact preference
- Offer to verify ownership at pickup

Avoid oversharing: do not include full ID numbers, full card numbers, full address, passwords, device passcodes, or other sensitive identifiers.

### Step 5 - Create the Contact Tracker

Make a tracker the user can fill in:

- Location or company
- Channel used
- Contact person if known
- Time contacted
- Summary of response
- Reference number
- Next follow-up time
- Pickup instructions

Encourage the user to keep messages short and log every response.

### Step 6 - Plan Safe Ownership Verification and Pickup

Help the user verify and retrieve safely:

- Bring a government ID if appropriate, but do not send full ID details in advance unless required by a trusted official process
- Describe a distinctive feature not visible in public photos
- Use a receipt, booking number, claim tag, or app trip record when relevant
- Meet at the venue, front desk, official lost-and-found counter, or other public staffed location
- Avoid paying unofficial "finder fees" or meeting strangers in isolated places
- If someone claims to have the item privately, ask for a non-sensitive proof photo and use a public handoff location

### Step 7 - Follow Up and Close the Loop

If no response arrives:

- Follow up once after a reasonable interval, such as the next business day or shift change
- Try a second official channel if available
- Ask whether items are transferred to a central lost-and-found office
- Set a cutoff date for continuing outreach
- If the item is high value or suspected stolen, suggest local official guidance rather than informal confrontation

## Output Format

Use this structure:

1. **Immediate Triage** - ordinary item vs. sensitive or urgent risk
2. **Item Fact Card** - safe description and last-known details
3. **Likely Location List** - ranked contact plan
4. **Message Templates** - venue, taxi/rideshare, hotel, or event versions as relevant
5. **Contact Tracker** - fillable log
6. **Safe Pickup Plan** - verification and handoff steps
7. **Follow-Up Schedule** - when to try again or stop

## Message Templates

### General Venue

Subject: Lost item inquiry from [date/time]

Hello, I may have left a [general item] at [venue area] around [time] on [date]. It is [safe description] with [safe distinctive detail]. Could you please check your lost and found and let me know if anything matching that description has been turned in? I can verify ownership in person or by providing an additional non-sensitive detail. Thank you.

### Hotel

Hello, I stayed under the name [name or booking reference if safe] on [date] and may have left a [general item] in [room/front desk/lobby/restaurant area]. It is [safe description]. Could housekeeping or lost and found check whether anything matching this was found? Please let me know the best way to verify ownership and arrange pickup or shipping.

### Taxi or Rideshare

Hello, I may have left a [general item] in a ride on [date] around [time], from [pickup area] to [dropoff area]. The item is [safe description] with [safe distinctive detail]. Could you please check with the driver or lost-property team? I can verify ownership with additional details if needed.

### Event or Conference

Hello, I attended [event name] on [date] and may have left a [general item] near [area/seat/booth]. It is [safe description]. Could you check the event lost and found or tell me where items are transferred after the event? I can provide additional verification if needed.

## Safety Boundaries

- Do not treat this as a wallet recovery, payment-card dispute, package claim, theft investigation, or insurance claim skill.
- Do not recommend sharing full ID numbers, full card numbers, passwords, device passcodes, home address, or complete serial numbers in outreach messages.
- Do not advise confronting suspected thieves or arranging isolated private meetups.
- Do not guarantee recovery or staff response times.
- For passports, government ID, payment cards, medications, work credentials, keys with address, or devices with sensitive data, recommend appropriate protective action through official providers or authorities.
- Keep outreach polite, concise, and easy for staff to act on.

## Acceptance Criteria

1. Response captures item facts and last-known location without exposing sensitive identifiers.
2. Response ranks likely venues or providers to contact.
3. Response provides concise outreach templates adapted to venue, taxi/rideshare, hotel, or event contexts.
4. Response includes a contact tracker.
5. Response includes safe ownership verification and pickup guidance.
6. Response stays distinct from lost-wallet, package-claim, theft-confrontation, and insurance-claim workflows.

## Example Prompts

Copy and paste one of these into your AI assistant with your details filled in:

1. **Left something at a cafe:** "I think I left my gray laptop charger at Blue Bottle Cafe on Main Street this afternoon around 3 PM. I was sitting at a table near the window. The charger has a small white label with my initials. Help me write a message to the cafe and track the response."

2. **Forgot bag in a taxi:** "I forgot a black canvas tote bag in a yellow taxi around 8 PM tonight. I took it from the train station to my hotel — about a 15-minute ride. The bag has a red zipper pull and some books inside. I have the taxi receipt with the medallion number. Draft a message and help me plan the follow-up."

3. **Hotel room item:** "I checked out of the Marriott near the airport this morning and realized I left my phone charger and a travel adapter plugged into the wall by the nightstand in room 412. I have my booking confirmation number. Help me contact the hotel and plan how to get the items back."

## Examples

### Example 1: Cafe Laptop Charger

**User says:** "I think I left my laptop charger at a cafe this afternoon."

**Skill guides:** Create a fact card with cafe name, time, table area, charger description, and safe distinctive details. Draft a short message asking staff to check lost and found. Add a tracker and pickup plan.

### Example 2: Taxi Bag

**User says:** "I forgot a tote bag in a taxi."

**Skill guides:** Capture trip time, pickup and dropoff areas, taxi company or app receipt, general bag description, and safe identifiers. Draft a taxi or rideshare lost-property message and warn against sharing sensitive contents in the first message.

### Example 3: Sensitive Item Boundary

**User says:** "My passport and wallet might be in the hotel room."

**Skill responds:** Treat as urgent. Help contact the hotel immediately, but also advise the user to follow official steps for passport and payment-card protection. Do not ask them to send full passport or card numbers in the hotel message.
