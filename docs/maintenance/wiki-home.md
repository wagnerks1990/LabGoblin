# LabGoblin

**Real Skills. Virtual Machines.**

LabGoblin is a classroom VM control plane. PostgreSQL owns desired state;
Proxmox mutations use durable jobs. Infrastructure credentials stay server-side.

The source-controlled documentation is the authoritative, versioned reference:

- [Documentation index](https://github.com/wagnerks1990/LabGoblin/blob/main/docs/index.md)
- [Student guide](https://github.com/wagnerks1990/LabGoblin/blob/main/docs/user-guide/student-workflow.md)
- [Instructor guide](https://github.com/wagnerks1990/LabGoblin/blob/main/docs/user-guide/instructor-workflow.md)
- [Deployment and rollback](https://github.com/wagnerks1990/LabGoblin/blob/main/docs/operations/updates.md)
- [Validation](https://github.com/wagnerks1990/LabGoblin/blob/main/docs/development/validation.md)
- [Security remediation](https://github.com/wagnerks1990/LabGoblin/blob/main/docs/security/dependency-remediation.md)

This public Wiki landing page is synchronized from
`docs/maintenance/wiki-home.md` after reviewed changes reach main. The workflow
publishes only this allowlisted page and preserves other manually maintained
Wiki pages. A missing or insufficient `WIKI_TOKEN` fails synchronization.
The Wiki must already be initialized through GitHub's **Create the first page**.
CI does not deploy classroom infrastructure or establish production readiness.
