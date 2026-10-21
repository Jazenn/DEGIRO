# Authenticated shared state and fast current valuation

The dashboard must be privately accessible across devices while the owner's PC is off. Route browser reads and writes through an authenticated web interface, keeping privileged credentials server-side and accepted Crypto Scale plans in shared durable storage; direct browser database access cannot provide the required access control and consistent state.

Retain the modular Python ledger and background Snapshot calculations, but refresh current prices through a separate bounded revaluation of reconciled positions, updating dependent figures together. This preserves fast current valuation without waiting for a history rebuild or duplicating transaction/fee interpretation; provider integration, exact calculation timing and latency remain verification gates before implementation handoff.

Context and approved direction: [Choose the frontend and backend overhaul boundaries](https://github.com/Jazenn/DEGIRO/issues/36). This amends the direct-query detail of ADR-0001 and preserves the modular structure in ADR-0002; it does not record a deployment or measured performance result.
