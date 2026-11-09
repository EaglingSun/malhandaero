import os
import tempfile

# 시험은 임시 폴더와 흉내 AI로 돈다. server를 가져오기 전에 정해야 한다.
os.environ["MALHAN_DATA"] = tempfile.mkdtemp(prefix="malhan-test-")
os.environ["MALHAN_FAKE_LLM"] = "1"
os.environ["MALHAN_FAMILY_CODE"] = "우리집"
