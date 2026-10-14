# Design notes

## Activity feed write failures (Part 3b)

If writing an activity record fails, the original change **rolls back**.

Task creates, status/assignee updates, and comment posts all run inside `transaction.atomic()` and call `log_activity()` in the same transaction. That keeps the audit trail consistent with project state: we never show a status change that has no matching feed entry (or a feed entry for a change that did not persist). For this product size, a failed activity insert is rare and better surfaced as a failed request than a silent audit gap.
