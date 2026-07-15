"""example/24_multimodal.py — Multimodal Pipeline verification."""
import sys, os, tempfile
from chainforge.core.multimodal import image_to_message, file_to_message, load_image_data
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

test_img = "/tmp/cf_test_img.png"
with open(test_img, "wb") as f:
    f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)

msg = image_to_message(test_img, "Analyze this")
c("image msg role", msg.role.value == "user")
c("image has parts", msg.parts is not None)

with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    f.write("test file content")
    tp = f.name

msg2 = file_to_message(tp, "Read this")
c("file msg role", msg2.role.value == "user")

os.unlink(tp)
os.unlink(test_img)
c("load_image_data exists", callable(load_image_data))

print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
