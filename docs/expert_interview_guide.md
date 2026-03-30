# Expert Interview Guide — Eagle Ridge Site Knowledge Elicitation

## Purpose

This guide supports structured interviews with experienced Eagle Ridge pilots to elicit tacit site knowledge for encoding as machine-readable heuristics in the LocalKnowledgeAgent.

Estimated interview duration: 60–90 minutes.
Format: Semi-structured, recorded with consent.

---

## Participant Criteria

- Minimum 50 hours logged at Eagle Ridge
- Active rating (USHPA P3 or equivalent) or instructor certification
- Willingness to be recorded and have anonymised knowledge encoded in the system

---

## Section 1: Site Mental Model (15 min)

1. "When you arrive at Eagle Ridge for the first time on a flying day, what are the first three things you look at or check?"

2. "Can you walk me through what a typical flyable day at Eagle Ridge looks like, hour by hour, from when you arrive to when you pack up?"

3. "What does the sky tell you at Eagle Ridge that you can't get from a forecast?"

4. "Are there any terrain features — ridges, bowls, trees, drainage — that you pay particular attention to? What do they tell you?"

---

## Section 2: Decision Triggers (20 min)

5. "What specific conditions make you say 'this is definitely flyable'? Can you give me numbers — wind speed, cloud cover, temperature?"

6. "What are your personal 'abort launch' conditions at Eagle Ridge? What would make you pack up even after you've rigged?"

7. "Have you ever been surprised by conditions at Eagle Ridge — either better or worse than expected? What happened?"

8. "Is there a time of day when Eagle Ridge is most reliable? Most dangerous?"

9. "How does the season affect your decision-making here? Are there months you avoid?"

---

## Section 3: Thermal Sensemaking (20 min)

10. "Where do thermals typically come from at Eagle Ridge? Can you point to spots on a map?"

11. "What conditions trigger the South Bowl? What are the signs you look for before committing to a South Bowl approach?"

12. "How do you distinguish between a weak thermal day and an overdeveloped day at Eagle Ridge? At what point does 'good cumulus' become 'dangerous cumulus'?"

13. "Are there any thermal cycles or patterns you've noticed — times when thermals fire in sequence, or quiet periods?"

14. "Have you ever seen rotor or mechanical turbulence at Eagle Ridge? Where, and under what conditions?"

---

## Section 4: Local Rules of Thumb (15 min)

15. "If you had to teach a P2 pilot a set of Eagle Ridge 'golden rules', what would they be?"

16. "Is there anything about Eagle Ridge that surprises pilots who are used to flying other sites? What do they get wrong?"

17. "Is there a wind direction or speed combination that is particularly dangerous at Eagle Ridge that might not be obvious from a forecast?"

18. "What's the most important thing to watch for during descent and approach to the LZ?"

---

## Section 5: System Feedback (10 min)

19. Show participant a sample system output (from `full_overlay_example.json`).
    "Looking at these recommendations — do any of them match your mental model of Eagle Ridge? Do any seem wrong or incomplete?"

20. "What information does this system provide that you find useful?"

21. "What important information is missing from this output?"

22. "If you were mentoring a student using this system, what would you tell them about its limitations?"

---

## Knowledge Encoding Notes

After the interview, extract heuristics in the following format for import:

```json
{
  "site_id": "eagle_ridge",
  "sub_region": "south_bowl",
  "wind_condition": "SW 12-25 km/h",
  "time_of_day": "11:00-14:00",
  "season": "spring-summer",
  "statement": "South Bowl thermals trigger when temp-dew spread exceeds 8°C and wind is SW 12-25 km/h. Approach from NE edge.",
  "confidence": 0.80,
  "source_expert": "P4_pilot_anonymised_01"
}
```

Import using:
```bash
uv run python scripts/import_knowledge.py --file eagle_ridge_heuristics.json
```

---

## Ethics and Consent

- Record only with explicit verbal and written consent.
- Anonymise pilot identifiers before encoding into the knowledge base.
- Pilots may request removal of their contributions at any time.
- This data is used solely for research and system development.
- No personally identifiable information is stored in the production database.
