Static Report Outline
=====================

Schema: _schemas/static_report.schema.yaml

Example only. Each report section must include a `section_status` and provenance.

Allowed section_status values:

- complete
- not_run
- not_available
- not_applicable
- blocked_by_privacy
- blocked_by_policy
- blocked_by_budget
- failed
- partial_success
- deferred_to_later_phase

```text
report_header:
 title: Report Title
 project_id: PROJECT-XXXX
 date: YYYY-MM-DD

executive_summary:
 section_status: complete|... (see allowed values)
 source_records: []
 source_artifacts: []
 summary: |
  One-paragraph summary
 missing_or_blocked_reason: optional text

current_decision:
 section_status: 
 source_records: []
 summary: |

dataset_summary:
 section_status:
 source_records: []
 summary: |

dataset_characterization:
 section_status:
 source_records: []
 summary: |

experiment_summary:
 section_status:
 source_records: []
 summary: |

model_comparison:
 section_status:
 source_records: []
 summary: |

performance_gap_diagnosis:
 section_status:
 source_records: []
 summary: |

learning_curves:
 section_status:
 source_records: []
 summary: |

error_analysis:
 section_status:
 source_records: []
 summary: |

cluster_or_latent_analysis:
 section_status:
 source_records: []
 summary: |

scientist_review:
 section_status:
 source_records: []
 summary: |

decision_record:
 section_status:
 source_records: []
 summary: |

knowledge_context:
 section_status:
 source_records: []
 summary: |

memory_context:
 section_status:
 source_records: []
 summary: |

recommendation_and_next_action:
 section_status:
 source_records: []
 summary: |

project_outcome:
 section_status:
 source_records: []
 summary: |

lessons_captured:
 section_status:
 source_records: []
 summary: |

foundation_opportunity:
 section_status:
 source_records: []
 summary: |

appendix:
 notes: |
  Attach logs, artifact links, and provenance.
```

Every `source_records`/`source_artifacts` entry should be a workspace path.
