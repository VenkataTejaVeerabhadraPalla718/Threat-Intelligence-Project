from dotenv import load_dotenv
load_dotenv()
import json
from pathlib import Path

answer = {
 "scenario":"A post has 10,000 comments.",
 "why_embedding_is_problematic":[
  "The post document becomes very large and approaches MongoDB's 16 MB BSON document limit.",
  "Every comment update may require rewriting a large embedded array.",
  "Frequently accessed post fields are coupled to a very large comment payload."
 ],
 "recommended_design":"Keep comments in a separate collection referenced by post_id; index post_id and paginate comments.",
 "query_pattern":"Find one post by post_id, then fetch comments by post_id with sort and limit."
}
print("3.2 TRY IT YOURSELF")
print(json.dumps(answer, indent=2))
Path("data").mkdir(exist_ok=True)
Path("data/activity_3_2_try_yourself.json").write_text(json.dumps(answer,indent=2),encoding="utf-8")
