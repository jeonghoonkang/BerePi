

Syntax:

scan [--delete|--import] START-DATE [END-DATE] query [queries...]

Examples:

tsdb scan --delete 1970/01/01-00:00:00 sum temperatures

tsdb scan --delete 1970/01/01-00:00:00 sum meterreadings
