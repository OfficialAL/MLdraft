import os
import heapq

def top_files(root='.', n=30):
    files = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                s = os.path.getsize(p)
            except Exception:
                continue
            files.append((s, p))
    return heapq.nlargest(n, files)

if __name__ == '__main__':
    for s, p in top_files('.'):
        print(f"{p} {s/1024/1024:.2f}MB")
