# PROJECT KNOWLEDGE INSTRUCTIONS

## FOR AI SESSIONS

When starting a new Claude session for AVIATOR project development:

### 1. ALWAYS LOAD THESE FILES
```
1. CLAUDE.md          - Core technical principles
2. ARCHITECTURE.md    - System structure
3. Current module     - File you're working on
```

### 2. CORE PRINCIPLES TO REMEMBER

#### DATA ACCURACY > SPEED
- Never sacrifice accuracy for performance
- Validate all data before processing
- Better to miss data than record wrong data

#### SHARED READER PATTERN
- ONE OCR reads, EVERYONE uses the data
- Never duplicate OCR operations
- Use shared memory for data distribution

#### BATCH EVERYTHING
- Never single database insert
- Buffer 50-100 records minimum
- Flush on interval or buffer full

#### ATOMIC TRANSACTIONS
- All betting operations must be atomic
- Use TransactionController for GUI operations
- Lock mechanism for every transaction

#### EVENT-DRIVEN ARCHITECTURE
- All inter-process communication via EventBus
- No direct process-to-process calls
- Pub/Sub pattern for loose coupling

### 3. WHEN CREATING NEW MODULES

#### ALWAYS INCLUDE
```python
"""
Module: [name]
Purpose: [clear description]
Version: [x.x]
"""

import logging
from typing import ...

class YourClass:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        # ... initialization
        
    def cleanup(self):
        """Always implement cleanup"""
        pass
        
    def get_stats(self):
        """Always implement stats"""
        return {}
```

#### NEVER DO
- Hard-code paths or coordinates
- Use global variables without locks
- Ignore error handling
- Skip logging
- Create tight coupling between modules

### 4. TESTING REQUIREMENTS

Before considering any module complete:
1. Unit tests for all public methods
2. Integration test with related modules
3. Performance benchmark
4. Memory leak check
5. Error recovery test

### 5. DOCUMENTATION STANDARDS

Every function must have:
```python
def function_name(param1: Type, param2: Type) -> ReturnType:
    """
    Brief description.
    
    Args:
        param1: Description
        param2: Description
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When this happens
    """
```

### 6. PERFORMANCE TARGETS

Critical operations must meet:
- OCR: < 15ms per read
- Database batch write: > 5000 records/sec
- Event processing: < 10ms
- Memory per worker: < 100MB

### 7. GIT WORKFLOW

Commit messages format:
```
[TYPE] Brief description

Detailed explanation if needed

- Bullet point 1
- Bullet point 2
```

Types: FEATURE, FIX, REFACTOR, PERF, DOCS, TEST

### 8. PRIORITY HIERARCHY

When making decisions, prioritize in this order:
1. **Data Accuracy** - Never compromise
2. **System Stability** - Must run 24/7
3. **Performance** - Meet targets
4. **Features** - Add incrementally
5. **UI/UX** - Polish last

### 9. QUESTIONS TO ASK

Before implementing anything:
1. Does this follow the Shared Reader pattern?
2. Am I using batch operations?
3. Is this loosely coupled via EventBus?
4. Have I handled all error cases?
5. Will this scale to 6+ bookmakers?

### 10. RED FLAGS TO AVOID

Stop immediately if you find yourself:
- Writing duplicate OCR code
- Doing single database inserts
- Creating direct process communication
- Hardcoding values
- Skipping error handling
- Not writing tests

## FOR HUMAN DEVELOPERS

When reviewing code or planning features:

### ASK THESE QUESTIONS
1. Is the architecture consistent with ARCHITECTURE.md?
2. Are core principles from CLAUDE.md followed?
3. Is the code testable and maintainable?
4. Will this work at scale (6+ bookmakers)?
5. Is error recovery implemented?

### CHECK THESE ITEMS
- [ ] Follows Shared Reader pattern
- [ ] Uses batch database operations
- [ ] Communicates via EventBus
- [ ] Has proper error handling
- [ ] Includes cleanup methods
- [ ] Has statistics tracking
- [ ] Documented properly
- [ ] Has unit tests

### REMEMBER
This is a long-term project focused on:
- **Reliability over features**
- **Data quality over quantity**  
- **Maintainability over cleverness**
- **Safety over aggressive profit**

The goal is a system that runs 24/7 with minimal intervention, collecting accurate data and executing safe betting strategies.