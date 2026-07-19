# HELLFIRE AI Solutions — RAG 01

Модуль 3. Інфраструктурний модуль, на якому будуються Office Agent і майбутні sector-агенти. Спершу — RAG над власною документацією TETA+PI/HELLFIRE (Data Room, Pitch Deck, технічні специфікації), з тестом retrieval-якості на реальних запитах.

**Dogfooding → шаблон:** універсальний RAG-pipeline (vector DB, chunking-стратегія, retrieval + generation prompt template), що підключається до будь-якого корпусу закритих даних клієнта.

**Відкриті технічні питання:**
- Vector DB: self-hosted (Qdrant) чи managed
- Хостинг з EU data residency (критично для DSGVO-продажу)

**Статус:** WIP — не розпочато.

**Ліцензія:** MIT.
