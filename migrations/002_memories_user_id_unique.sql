-- The Basic Memory Layer stores many records per owner; memory_id is the key.
drop index if exists memories_user_id_unique;
