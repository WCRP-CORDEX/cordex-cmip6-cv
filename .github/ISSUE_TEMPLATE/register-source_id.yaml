name: Register source_id
description: Register a new model for the CORDEX CV.
title: "[source_id]: "
labels: ["model registratrion"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time!
  - type: input
    id: contact
    attributes:
      label: Contact Details
      description: How can we get in touch with you if we need more info?
      placeholder: ex. email@example.com
    validations:
      required: false
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: Also tell us, what did you expect to happen?
      placeholder: Tell us what you see!
      value: "A bug happened!"
    validations:
      required: true
  - type: dropdown
    id: license
    attributes:
      label: What license do you choose?
      multiple: false
      options:
        - CC0
        - CC BY 4.0
  - type: textarea
    id: logs
    attributes:
      label: Relevant log output
      description: Please copy and paste any relevant log output. This will be automatically formatted into code, so no need for backticks.
      render: shell
