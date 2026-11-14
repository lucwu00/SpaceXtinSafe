import os, tempfile
os.environ.setdefault("SXS_USAGE_LOG", os.path.join(tempfile.mkdtemp(), "usage.jsonl"))  # tests never write to the server's usage log
