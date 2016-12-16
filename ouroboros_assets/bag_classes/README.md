#bag_classes

This folder contains python classes used during ingest to create bags.  These classes are dropped in during the `ingestWorkspace()` workflow, after a job has been created, the metadata parsed, and the intellectual objects inserted into MySQL.  These classes might be applicable across collections, but might also be collection specific.

The following diagram outlines their place in the workflow:
![diagram](Bag_Creation_Class.png?raw=true "Bag_Creation_Logo")