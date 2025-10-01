import json

def example_json_schema() -> str:
    schema = {
        "tables": [
            {
                "table_name": "`bigquery-public-data.github_repos.commits`",
                "table_columns": [
                    {
                        "name": "commit",
                        "type": "STRING",
                        "mode": "REQUIRED",
                        "description": "SHA of the commit"
                    },
                    {
                        "name": "tree",
                        "type": "STRING",
                        "mode": "NULLABLE",
                        "description": "SHA of the tree object for the commit"
                    },
                    {
                        "name": "parent",
                        "type": "STRING",
                        "mode": "REPEATED",
                        "description": "SHA of the parent commits"
                    },
                    {
                        "name": "author",
                        "type": "RECORD",
                        "mode": "NULLABLE",
                        "description": "Information about the commit author",
                        "fields": [
                        {"name": "name", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "email", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "time_sec", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "tz_offset", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "date", "type": "TIMESTAMP", "mode": "NULLABLE"}
                        ]
                    },
                    {
                        "name": "committer",
                        "type": "RECORD",
                        "mode": "NULLABLE",
                        "description": "Information about the committer",
                        "fields": [
                        {"name": "name", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "email", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "time_sec", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "tz_offset", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "date", "type": "TIMESTAMP", "mode": "NULLABLE"}
                        ]
                    },
                    {
                        "name": "message",
                        "type": "STRING",
                        "mode": "NULLABLE",
                        "description": "Commit message"
                    },
                    {
                        "name": "difference",
                        "type": "RECORD",
                        "mode": "REPEATED",
                        "description": "File differences introduced by the commit",
                        "fields": [
                        {"name": "old_mode", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "new_mode", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "old_path", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "new_path", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "old_sha1", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "new_sha1", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "old_repo", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "new_repo", "type": "STRING", "mode": "NULLABLE"}
                        ]
                    },
                    {
                        "name": "trailer",
                        "type": "RECORD",
                        "mode": "REPEATED",
                        "description": "Key-value pairs from the commit message footer",
                        "fields": [
                        {"name": "key", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "value", "type": "STRING", "mode": "NULLABLE"}
                        ]
                    },
                    {
                        "name": "repo_name",
                        "type": "STRING",
                        "mode": "REPEATED",
                        "description": "Full name of the repository (e.g., 'owner/repo')"
                    }
                    ]
            },
            {
                "table_name": "`bigquery-public-data.github_repos.licenses`",
                "table_columns": [
                    {
                        "name": "repo_name",
                        "type": "STRING",
                        "mode": "REQUIRED",
                        "description": "Full name of the repository (e.g., 'owner/repo')"
                    },
                    {
                        "name": "license",
                        "type": "RECORD",
                        "mode": "REPEATED",
                        "description": "Information about licenses detected in the repository",
                        "fields": [
                        {"name": "name", "type": "STRING", "mode": "NULLABLE", "description": "Name of the license"},
                        {"name": "spdx_id", "type": "STRING", "mode": "NULLABLE", "description": "SPDX identifier for the license"}
                        ]
                    }
                    ]
            },
            {
                "table_name": "`bigquery-public-data.github_repos.sample_repos`",
                "table_columns": [
                    {
                        "name": "repo_name",
                        "type": "STRING",
                        "mode": "REQUIRED",
                        "description": "Full name of the repository (e.g., 'owner/repo')"
                    },
                    {
                        "name": "watch_count",
                        "type": "INTEGER",
                        "mode": "NULLABLE",
                        "description": "Number of watchers"
                    }
                    ]
            },
            {
                "table_name": "`bigquery-public-data.github_repos.sample_commits`",
                "table_columns": [
                    {
                        "name": "commit",
                        "type": "STRING",
                        "mode": "REQUIRED",
                        "description": "SHA of the commit"
                    },
                    {
                        "name": "tree",
                        "type": "STRING",
                        "mode": "NULLABLE",
                        "description": "SHA of the tree object for the commit"
                    },
                    {
                        "name": "parent",
                        "type": "STRING",
                        "mode": "REPEATED",
                        "description": "SHA of the parent commits"
                    },
                    {
                        "name": "author",
                        "type": "RECORD",
                        "mode": "NULLABLE",
                        "description": "Information about the commit author",
                        "fields": [
                        {"name": "name", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "email", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "time_sec", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "tz_offset", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "date", "type": "TIMESTAMP", "mode": "NULLABLE"}
                        ]
                    },
                    {
                        "name": "committer",
                        "type": "RECORD",
                        "mode": "NULLABLE",
                        "description": "Information about the committer",
                        "fields": [
                        {"name": "name", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "email", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "time_sec", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "tz_offset", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "date", "type": "TIMESTAMP", "mode": "NULLABLE"}
                        ]
                    },
                    {
                        "name": "message",
                        "type": "STRING",
                        "mode": "NULLABLE",
                        "description": "Commit message"
                    },
                    {
                        "name": "difference",
                        "type": "RECORD",
                        "mode": "REPEATED",
                        "description": "File differences introduced by the commit",
                        "fields": [
                        {"name": "old_mode", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "new_mode", "type": "INTEGER", "mode": "NULLABLE"},
                        {"name": "old_path", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "new_path", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "old_sha1", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "new_sha1", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "old_repo", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "new_repo", "type": "STRING", "mode": "NULLABLE"}
                        ]
                    },
                    {
                        "name": "trailer",
                        "type": "RECORD",
                        "mode": "REPEATED",
                        "description": "Key-value pairs from the commit message footer",
                        "fields": [
                        {"name": "key", "type": "STRING", "mode": "NULLABLE"},
                        {"name": "value", "type": "STRING", "mode": "NULLABLE"}
                        ]
                    },
                    {
                        "name": "repo_name",
                        "type": "STRING",
                        "mode": "NULLABLE",
                        "description": "Full name of the repository (e.g., 'owner/repo')"
                    }
                    ]
            },
        ],
        "dialect": "bigquery",
    }
    return json.dumps(schema)
