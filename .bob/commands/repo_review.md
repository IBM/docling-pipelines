---
Description: Run a Repo Review
---
This needs to be run in the orchestration mode. So switch modes if required. Before starting the review, please ensure that the following are in place:
- The user has the latest code pulled in the main branch (git pull)
- There are no dead folders/files. Local codebase should be on the same level as the remote repo main branch(This can be changed if the user has made changes to the codebase in local that they want to review). 

Please look across this codebase and look for major inconsistencies, issues, etc.. - I want an architectural review and a detailed code review. find me some "dirt" - I know it's there. Where's the dead code? where's the broken abstractions? What is the dominant architecture? (hexagonal, something else?) How true is the code to the archtecture? include succinct code snippets with file attribution where necessary to prove a point.  
don't make changes, Whenever you run the review create a new folder in the arch/docs folder. name it after the date and time of the review. Any further review you run ensure that you are comparing it the previous review to ensure standardisation reports.  
go deep - one md file (at least) per source directory, and do it via todo list I want you to build. once you have done that, come back up and give an overall summary, pointing at the other md files for details.

Extra instructions: Look at the test coverage and the test folder as well. Ignore any examples folders as its not part of the actual code base. If you find any unimplemented code do not include it in the actual grade of the repo but add a mention to the report in a new file.  