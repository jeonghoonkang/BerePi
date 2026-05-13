# third_party

Place the zero-native framework source tree here if you want the local default build path to work:

```bash
git clone https://github.com/vercel-labs/zero-native.git third_party/zero-native
```

You can also override the framework path at build time:

```bash
zig build run -Dzero-native-path=/absolute/path/to/zero-native
```
