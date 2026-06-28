# Acceptance Tests - Venue Lost Item Recovery Kit

## Overview
- **Skill:** Venue Lost Item Recovery Kit
- **Slug:** venue-lost-item-recovery-kit
- **Priority:** P2
- **Project:** daily-50-skills-2026-05-08
- **Total Tests:** 8

## AT-1: Item facts are captured safely.
- **Check:** Response asks for item type, general description, last-known time/place, route, and safe identifiers.
- **Expected:** It avoids requesting full ID numbers, card numbers, passwords, passcodes, home address, or complete serial numbers for outreach.
- **Pass:** Output demonstrates compliance with this criterion.

## AT-2: Urgency triage is included.
- **Check:** Response identifies when sensitive items require protective action.
- **Expected:** Payment cards, passports, government IDs, medications, keys with address, work badges, phones, laptops, and confidential documents are flagged appropriately.
- **Pass:** Output demonstrates compliance with this criterion.

## AT-3: Likely locations are ranked.
- **Check:** Response creates a prioritized contact list.
- **Expected:** Last confirmed location, staff lost-and-found, transport provider, hotel desk, event desk, or central lost-and-found are considered as relevant.
- **Pass:** Output demonstrates compliance with this criterion.

## AT-4: Outreach templates are concise and context-specific.
- **Check:** Response provides messages for venue, taxi/rideshare, hotel, event, or similar contexts as needed.
- **Expected:** Templates include date, approximate time, location area, general item description, safe distinguishing detail, and ownership verification offer.
- **Pass:** Output demonstrates compliance with this criterion.

## AT-5: Contact tracker is included.
- **Check:** Response includes a fillable tracker.
- **Expected:** Tracker fields include location, channel, time contacted, response, reference number, next follow-up, and pickup instructions.
- **Pass:** Output demonstrates compliance with this criterion.

## AT-6: Safe pickup and verification are covered.
- **Check:** Response recommends public or official pickup locations and non-sensitive proof of ownership.
- **Expected:** It avoids isolated meetups, unofficial payments, and oversharing sensitive identifiers.
- **Pass:** Output demonstrates compliance with this criterion.

## AT-7: Distinct workflow boundary.
- **Check:** Response does not turn into a package claim, wallet dispute, theft confrontation, or insurance claim workflow.
- **Expected:** It remains focused on venue, taxi, hotel, rideshare, event, and lost-and-found outreach.
- **Pass:** Output demonstrates compliance with this criterion.

## AT-8: No-code compliance.
- **Check:** No executable code, scripts, API calls, external handlers, network requirements, or credential requests.
- **Expected:** skill.json has `hasExecutableCode: false`, `requires_api: false`, `no_code_execution: true`, `no_network: true`, and `no_credentials: true`.
- **Pass:** Skill is purely document/prompt-flow with no executable components.

## Clean Scan Evidence

- **Executable code:** None (prompt-only, noExec)
- **API calls:** None required
- **Network access:** No (document-only)
- **Credentials:** None stored or requested
- **Secrets or .env:** None
- **Logs or temp files:** None
- **Package files or scripts:** None
- **CJK/non-ASCII:** None — English/ASCII only
- **Safety scan:** Clean — venue outreach and lost-property logistics only; no wallet/payment-card/identity theft/investigation workflows; explicitly avoids sensitive identifiers in outreach templates; safe pickup and ownership verification guidance included

## Install-First Success Path

- **Input:** User says "I think I left my laptop charger at a cafe this afternoon. It's a gray 65W charger with a white label showing my initials. I was sitting near the window at Blue Bottle around 3 PM."
- **Steps:** Skill triages urgency (ordinary item, no sensitive contents) → builds an item fact card with safe description and last-known details → ranks likely locations (cafe first, then transportation if relevant) → provides a venue-adapted outreach message with date/time/area/general description/safe distinctive detail → creates a contact tracker with location, channel, response, reference number, and follow-up timing → plans safe pickup with ownership verification.
- **Output:** An item fact card, a ranked contact plan, a ready-to-send message template, a fillable contact tracker, and a safe pickup plan — all focused on lost-property logistics without exposing sensitive identifiers.
