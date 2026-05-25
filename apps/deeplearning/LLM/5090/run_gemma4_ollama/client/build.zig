const std = @import("std");

const PlatformOption = enum {
    auto,
    null,
    macos,
    linux,
    windows,
};

const TraceOption = enum {
    off,
    events,
    runtime,
    all,
};

const WebEngineOption = enum {
    system,
    chromium,
};

const PackageTarget = enum {
    macos,
    windows,
    linux,
};

const default_zero_native_path = "third_party/zero-native";
const app_exe_name = "gemma4promptclient";

pub fn build(b: *std.Build) void {
    const target = zeroNativeTarget(b);
    const optimize = b.standardOptimizeOption(.{});
    const platform_option = b.option(PlatformOption, "platform", "Desktop backend: auto, null, macos, linux, windows") orelse .auto;
    const trace_option = b.option(TraceOption, "trace", "Trace output: off, events, runtime, all") orelse .events;
    const debug_overlay = b.option(bool, "debug-overlay", "Enable debug overlay output") orelse false;
    const automation_enabled = b.option(bool, "automation", "Enable zero-native automation artifacts") orelse false;
    const js_bridge_enabled = b.option(bool, "js-bridge", "Enable optional JavaScript bridge stubs") orelse false;
    const web_engine_override = b.option(WebEngineOption, "web-engine", "Override app.zon web engine: system, chromium");
    const cef_dir_override = b.option([]const u8, "cef-dir", "Override CEF root directory for Chromium builds");
    const cef_auto_install_override = b.option(bool, "cef-auto-install", "Override app.zon CEF auto-install setting");
    const package_target = b.option(PackageTarget, "package-target", "Package target: macos, windows, linux") orelse .macos;
    const zero_native_path = b.option([]const u8, "zero-native-path", "Path to the zero-native framework checkout") orelse default_zero_native_path;
    const optimize_name = @tagName(optimize);
    const selected_platform: PlatformOption = switch (platform_option) {
        .auto => if (target.result.os.tag == .macos) .macos else if (target.result.os.tag == .linux) .linux else if (target.result.os.tag == .windows) .windows else .null,
        else => platform_option,
    };
    if (selected_platform == .macos and target.result.os.tag != .macos) {
        @panic("-Dplatform=macos requires a macOS target");
    }
    if (selected_platform == .linux and target.result.os.tag != .linux) {
        @panic("-Dplatform=linux requires a Linux target");
    }
    if (selected_platform == .windows and target.result.os.tag != .windows) {
        @panic("-Dplatform=windows requires a Windows target");
    }
    const app_web_engine = appWebEngineConfig();
    const web_engine = web_engine_override orelse app_web_engine.web_engine;
    const cef_dir = cef_dir_override orelse defaultCefDir(selected_platform, app_web_engine.cef_dir);
    const cef_auto_install = cef_auto_install_override orelse app_web_engine.cef_auto_install;
    if (web_engine == .chromium and selected_platform == .null) {
        @panic("-Dweb-engine=chromium requires -Dplatform=macos, linux, or windows");
    }

    const zero_native_mod = zeroNativeModule(b, target, optimize, zero_native_path);
    const options = b.addOptions();
    options.addOption([]const u8, "platform", switch (selected_platform) {
        .auto => unreachable,
        .null => "null",
        .macos => "macos",
        .linux => "linux",
        .windows => "windows",
    });
    options.addOption([]const u8, "trace", @tagName(trace_option));
    options.addOption([]const u8, "web_engine", @tagName(web_engine));
    options.addOption(bool, "debug_overlay", debug_overlay);
    options.addOption(bool, "automation", automation_enabled);
    options.addOption(bool, "js_bridge", js_bridge_enabled);
    const options_mod = options.createModule();

    const runner_mod = localModule(b, target, optimize, "src/runner.zig");
    runner_mod.addImport("zero-native", zero_native_mod);
    runner_mod.addImport("build_options", options_mod);

    const app_mod = localModule(b, target, optimize, "src/main.zig");
    app_mod.addImport("zero-native", zero_native_mod);
    app_mod.addImport("runner", runner_mod);
    const exe = b.addExecutable(.{
        .name = app_exe_name,
        .root_module = app_mod,
    });
    linkPlatform(b, target, app_mod, exe, selected_platform, web_engine, zero_native_path, cef_dir, cef_auto_install);
    b.installArtifact(exe);

    const frontend_install = b.addSystemCommand(&.{ "npm", "install", "--prefix", "frontend" });
    const frontend_install_step = b.step("frontend-install", "Install frontend dependencies");
    frontend_install_step.dependOn(&frontend_install.step);

    const frontend_build = b.addSystemCommand(&.{ "npm", "--prefix", "frontend", "run", "build" });
    frontend_build.step.dependOn(&frontend_install.step);
    const frontend_step = b.step("frontend-build", "Build the frontend");
    frontend_step.dependOn(&frontend_build.step);

    const run = b.addRunArtifact(exe);
    run.step.dependOn(&frontend_build.step);
    addCefRuntimeRunFiles(b, target, run, exe, web_engine, cef_dir);
    const run_step = b.step("run", "Run the app");
    run_step.dependOn(&run.step);

    const dev = b.addSystemCommand(&.{ "zero-native", "dev", "--manifest", "app.zon", "--binary" });
    dev.addFileArg(exe.getEmittedBin());
    dev.step.dependOn(&exe.step);
    dev.step.dependOn(&frontend_install.step);
    const dev_step = b.step("dev", "Run the frontend dev server and native shell");
    dev_step.dependOn(&dev.step);

    const package = b.addSystemCommand(&.{
        "zero-native",
        "package",
        "--target",
        @tagName(package_target),
        "--manifest",
        "app.zon",
        "--assets",
        "frontend/dist",
        "--optimize",
        optimize_name,
        "--output",
        b.fmt("zig-out/package/{s}-0.1.0-{s}-{s}{s}", .{ app_exe_name, @tagName(package_target), optimize_name, packageSuffix(package_target) }),
        "--binary",
    });
    package.addFileArg(exe.getEmittedBin());
    package.addArgs(&.{ "--web-engine", @tagName(web_engine), "--cef-dir", cef_dir });
    if (cef_auto_install) package.addArg("--cef-auto-install");
    package.step.dependOn(&exe.step);
    package.step.dependOn(&frontend_build.step);
    const package_step = b.step("package", "Create a local package artifact");
    package_step.dependOn(&package.step);

    const tests = b.addTest(.{ .root_module = app_mod });
    const test_step = b.step("test", "Run tests");
    test_step.dependOn(&b.addRunArtifact(tests).step);
}

fn zeroNativeTarget(b: *std.Build) std.Build.ResolvedTarget {
    const target = b.standardTargetOptions(.{});
    if (target.result.os.tag != .macos) return target;

    if (b.sysroot == null) {
        b.sysroot = macosSdkPath(b) orelse b.sysroot;
    }

    var query = target.query;
    query.os_tag = .macos;
    query.os_version_min = .{ .semver = .{ .major = 11, .minor = 0, .patch = 0 } };
    return b.resolveTargetQuery(query);
}

fn macosSdkPath(b: *std.Build) ?[]const u8 {
    if (b.graph.environ_map.get("SDKROOT")) |sdkroot| {
        if (sdkroot.len > 0) return sdkroot;
    }

    const result = std.process.run(b.allocator, b.graph.io, .{
        .argv = &.{ "xcrun", "--sdk", "macosx", "--show-sdk-path" },
        .stdout_limit = .limited(4096),
        .stderr_limit = .limited(4096),
    }) catch return null;
    defer b.allocator.free(result.stderr);
    if (result.term != .exited or result.term.exited != 0) {
        b.allocator.free(result.stdout);
        return null;
    }
    return std.mem.trimEnd(u8, result.stdout, "\r\n");
}

fn localModule(b: *std.Build, target: std.Build.ResolvedTarget, optimize: std.builtin.OptimizeMode, path: []const u8) *std.Build.Module {
    return b.createModule(.{
        .root_source_file = b.path(path),
        .target = target,
        .optimize = optimize,
    });
}

fn zeroNativePath(b: *std.Build, zero_native_path: []const u8, sub_path: []const u8) std.Build.LazyPath {
    return .{ .cwd_relative = b.pathJoin(&.{ zero_native_path, sub_path }) };
}

fn zeroNativeModule(b: *std.Build, target: std.Build.ResolvedTarget, optimize: std.builtin.OptimizeMode, zero_native_path: []const u8) *std.Build.Module {
    const geometry_mod = externalModule(b, target, optimize, zero_native_path, "src/primitives/geometry/root.zig");
    const assets_mod = externalModule(b, target, optimize, zero_native_path, "src/primitives/assets/root.zig");
    const app_dirs_mod = externalModule(b, target, optimize, zero_native_path, "src/primitives/app_dirs/root.zig");
    const trace_mod = externalModule(b, target, optimize, zero_native_path, "src/primitives/trace/root.zig");
    const app_manifest_mod = externalModule(b, target, optimize, zero_native_path, "src/primitives/app_manifest/root.zig");
    const diagnostics_mod = externalModule(b, target, optimize, zero_native_path, "src/primitives/diagnostics/root.zig");
    const platform_info_mod = externalModule(b, target, optimize, zero_native_path, "src/primitives/platform_info/root.zig");
    const json_mod = externalModule(b, target, optimize, zero_native_path, "src/primitives/json/root.zig");
    const debug_mod = externalModule(b, target, optimize, zero_native_path, "src/debug/root.zig");
    debug_mod.addImport("app_dirs", app_dirs_mod);
    debug_mod.addImport("trace", trace_mod);

    const zero_native_mod = externalModule(b, target, optimize, zero_native_path, "src/root.zig");
    zero_native_mod.addImport("geometry", geometry_mod);
    zero_native_mod.addImport("assets", assets_mod);
    zero_native_mod.addImport("app_dirs", app_dirs_mod);
    zero_native_mod.addImport("trace", trace_mod);
    zero_native_mod.addImport("app_manifest", app_manifest_mod);
    zero_native_mod.addImport("diagnostics", diagnostics_mod);
    zero_native_mod.addImport("platform_info", platform_info_mod);
    zero_native_mod.addImport("json", json_mod);
    return zero_native_mod;
}

fn externalModule(b: *std.Build, target: std.Build.ResolvedTarget, optimize: std.builtin.OptimizeMode, zero_native_path: []const u8, path: []const u8) *std.Build.Module {
    return b.createModule(.{
        .root_source_file = zeroNativePath(b, zero_native_path, path),
        .target = target,
        .optimize = optimize,
    });
}

fn linkPlatform(b: *std.Build, target: std.Build.ResolvedTarget, app_mod: *std.Build.Module, exe: *std.Build.Step.Compile, platform: PlatformOption, web_engine: WebEngineOption, zero_native_path: []const u8, cef_dir: []const u8, cef_auto_install: bool) void {
    if (platform == .macos) {
        switch (web_engine) {
            .system => {
                const sdk_include = if (b.sysroot) |sysroot| b.fmt("-I{s}/usr/include", .{sysroot}) else "";
                const flags: []const []const u8 = if (b.sysroot) |sysroot| &.{ "-fobjc-arc", "-ObjC", "-mmacosx-version-min=11.0", "-isysroot", sysroot, sdk_include } else &.{ "-fobjc-arc", "-ObjC", "-mmacosx-version-min=11.0" };
                app_mod.addCSourceFile(.{ .file = zeroNativePath(b, zero_native_path, "src/platform/macos/appkit_host.m"), .flags = flags });
                app_mod.linkFramework("WebKit", .{});
            },
            .chromium => {
                const cef_check = addCefCheck(b, target, cef_dir);
                if (cef_auto_install) {
                    const cef_auto = b.addSystemCommand(&.{ "zero-native", "cef", "install", "--dir", cef_dir });
                    cef_check.step.dependOn(&cef_auto.step);
                }
                exe.step.dependOn(&cef_check.step);
                const include_arg = b.fmt("-I{s}", .{cef_dir});
                app_mod.addCSourceFile(.{ .file = zeroNativePath(b, zero_native_path, "src/platform/macos/cef_host.mm"), .flags = &.{ "-fobjc-arc", "-ObjC++", "-std=c++17", "-mmacosx-version-min=11.0", include_arg } });
                exe.addObjectFile(zeroNativePath(b, zero_native_path, "third_party/cef/macos/libcef_dll_wrapper.a"));
                exe.addLibraryPath(.{ .cwd_relative = b.pathJoin(&.{ cef_dir, "Release" }) });
                exe.linkSystemLibrary("cef", .{});
                exe.linkFramework("AppKit", .{});
                exe.linkFramework("CoreFoundation", .{});
                exe.linkFramework("Foundation", .{});
            },
        }
        exe.linkFramework("AppKit", .{});
        exe.linkFramework("CoreFoundation", .{});
        exe.linkFramework("Foundation", .{});
    } else if (platform == .linux) {
        if (web_engine == .system) {
            app_mod.addCSourceFile(.{ .file = zeroNativePath(b, zero_native_path, "src/platform/linux/webkitgtk_host.c"), .flags = &.{"-std=c11"} });
        } else {
            const cef_check = addCefCheck(b, target, cef_dir);
            if (cef_auto_install) {
                const cef_auto = b.addSystemCommand(&.{ "zero-native", "cef", "install", "--dir", cef_dir });
                cef_check.step.dependOn(&cef_auto.step);
            }
            exe.step.dependOn(&cef_check.step);
            app_mod.addCSourceFile(.{ .file = zeroNativePath(b, zero_native_path, "src/platform/linux/cef_host.cc"), .flags = &.{ "-std=c++17", b.fmt("-I{s}", .{cef_dir}) } });
            exe.addObjectFile(zeroNativePath(b, zero_native_path, "third_party/cef/linux/libcef_dll_wrapper.a"));
            exe.addLibraryPath(.{ .cwd_relative = b.pathJoin(&.{ cef_dir, "Release" }) });
            exe.linkSystemLibrary("cef", .{});
        }
        exe.linkSystemLibrary("gtk-3", .{ .use_pkg_config = .force });
        exe.linkSystemLibrary("webkit2gtk-4.1", .{ .use_pkg_config = if (web_engine == .system) .force else .no });
        exe.linkSystemLibrary("javascriptcoregtk-4.1", .{ .use_pkg_config = if (web_engine == .system) .force else .no });
    } else if (platform == .windows) {
        if (web_engine == .system) {
            app_mod.addCSourceFile(.{ .file = zeroNativePath(b, zero_native_path, "src/platform/windows/webview2_host.c"), .flags = &.{"-std=c11"} });
        } else {
            const cef_check = addCefCheck(b, target, cef_dir);
            if (cef_auto_install) {
                const cef_auto = b.addSystemCommand(&.{ "zero-native", "cef", "install", "--dir", cef_dir });
                cef_check.step.dependOn(&cef_auto.step);
            }
            exe.step.dependOn(&cef_check.step);
            app_mod.addCSourceFile(.{ .file = zeroNativePath(b, zero_native_path, "src/platform/windows/cef_host.cc"), .flags = &.{ "-std=c++17", b.fmt("-I{s}", .{cef_dir}) } });
            exe.addObjectFile(zeroNativePath(b, zero_native_path, "third_party/cef/windows/libcef_dll_wrapper.lib"));
            exe.addLibraryPath(.{ .cwd_relative = b.pathJoin(&.{ cef_dir, "Release" }) });
            exe.linkSystemLibrary("libcef", .{});
        }
        exe.linkSystemLibrary("ole32", .{});
        exe.linkSystemLibrary("shell32", .{});
        exe.linkSystemLibrary("user32", .{});
        exe.linkSystemLibrary("gdi32", .{});
    }
}

fn addCefCheck(b: *std.Build, target: std.Build.ResolvedTarget, cef_dir: []const u8) *std.Build.Step.Run {
    const platform = switch (target.result.os.tag) {
        .macos => "macos",
        .linux => "linux",
        .windows => "windows",
        else => "unknown",
    };
    return b.addSystemCommand(&.{ "zero-native", "cef", "check", "--platform", platform, "--dir", cef_dir });
}

fn addCefRuntimeRunFiles(b: *std.Build, target: std.Build.ResolvedTarget, run: *std.Build.Step.Run, exe: *std.Build.Step.Compile, web_engine: WebEngineOption, cef_dir: []const u8) void {
    _ = b;
    _ = target;
    _ = exe;
    if (web_engine == .chromium) {
        run.addArgs(&.{ "--cef-runtime-dir", cef_dir });
    }
}

fn appWebEngineConfig() struct { web_engine: WebEngineOption, cef_dir: []const u8, cef_auto_install: bool } {
    return .{
        .web_engine = .system,
        .cef_dir = "third_party/cef/macos",
        .cef_auto_install = false,
    };
}

fn defaultCefDir(platform: PlatformOption, fallback: []const u8) []const u8 {
    return switch (platform) {
        .macos => "third_party/cef/macos",
        .linux => "third_party/cef/linux",
        .windows => "third_party/cef/windows",
        else => fallback,
    };
}

fn packageSuffix(target: PackageTarget) []const u8 {
    return switch (target) {
        .macos => ".app",
        .windows => ".zip",
        .linux => ".tar.gz",
    };
}
