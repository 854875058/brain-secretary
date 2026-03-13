#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "ops" / "deployment_manifest.json"
WINDOWS_DETACHED_FLAGS = 0
if os.name == "nt":
    WINDOWS_DETACHED_FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS


class OpsError(RuntimeError):
    pass


class OpsManager:
    def __init__(self, dry_run: bool = False):
        self.root = ROOT
        self.manifest = self._load_manifest()
        self.platform = "windows" if os.name == "nt" else "linux"
        self.platform_cfg = self.manifest["platforms"][self.platform]
        self.dry_run = dry_run

    def _load_manifest(self) -> dict[str, Any]:
        with MANIFEST_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _run(self, cmd: list[str], *, cwd: Path | None = None, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
        printable = shlex.join(cmd)
        if self.dry_run:
            print(f"[dry-run] {printable}")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            check=check,
            capture_output=capture,
        )

    def _spawn_detached(self, cmd: list[str], *, cwd: Path, log_file: Path | None = None) -> None:
        printable = shlex.join(cmd)
        if self.dry_run:
            print(f"[dry-run] {printable}")
            return
        stdout_handle = subprocess.DEVNULL
        stderr_handle = subprocess.DEVNULL
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handle = log_file.open("ab")
            stdout_handle = handle
            stderr_handle = subprocess.STDOUT
        creationflags = WINDOWS_DETACHED_FLAGS if self.platform == "windows" else 0
        subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=self.platform != "windows",
            creationflags=creationflags,
        )

    def _component_meta(self, component: str) -> dict[str, Any]:
        common = self.manifest["components"][component]
        platform_specific = self.platform_cfg["components"].get(component, {})
        merged = dict(common)
        merged.update(platform_specific)
        return merged

    def _resolve_target(self, target: str | None) -> list[str]:
        groups = self.platform_cfg["groups"]
        aliases = {
            None: "all",
            "all": "all",
            "backend": "backend",
            "back": "backend",
            "frontend": "frontend",
            "front": "frontend",
        }
        normalized = aliases.get(target, target)
        if normalized in groups:
            return list(groups[normalized])
        if normalized in self.platform_cfg["components"]:
            return [normalized]
        valid = sorted(set(groups) | set(self.platform_cfg["components"]))
        raise OpsError(f"未知目标: {target}. 可选: {', '.join(valid)}")

    def _port_open(self, host: str, port: int, timeout: float = 0.6) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def _port_summary(self, component: str) -> list[tuple[str, str, int, bool]]:
        meta = self._component_meta(component)
        result = []
        for item in meta.get("ports", []):
            host = item.get("host", "127.0.0.1")
            port = int(item["port"])
            result.append((item.get("name", "tcp"), host, port, self._port_open(host, port)))
        return result

    def _linux_system_scope(self, component: str) -> bool:
        return bool(self._component_meta(component).get("system_scope", False))

    def _linux_systemctl_base(self, component: str) -> list[str]:
        if self._linux_system_scope(component):
            return ["systemctl"]
        return ["systemctl", "--user"]

    def _linux_journalctl_base(self, component: str) -> list[str]:
        if self._linux_system_scope(component):
            return ["journalctl"]
        return ["journalctl", "--user"]

    def _linux_status(self, component: str) -> dict[str, str]:
        unit = self._component_meta(component).get("unit")
        if not unit:
            return {"active": "n/a", "enabled": "n/a", "pid": "-"}
        systemctl = self._linux_systemctl_base(component)
        active = self._run(systemctl + ["is-active", unit], check=False).stdout.strip() or "unknown"
        enabled = self._run(systemctl + ["is-enabled", unit], check=False).stdout.strip() or "unknown"
        pid = self._run(systemctl + ["show", "-p", "MainPID", "--value", unit], check=False).stdout.strip() or "0"
        return {"active": active, "enabled": enabled, "pid": pid}

    def _windows_listening_pids(self, port: int) -> list[str]:
        result = self._run(["netstat", "-ano", "-p", "tcp"], check=False)
        pids: set[str] = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 5 or parts[0].upper() != "TCP":
                continue
            local_addr = parts[1]
            state = parts[3].upper()
            pid = parts[4]
            if state != "LISTENING":
                continue
            if local_addr.rsplit(":", 1)[-1] == str(port):
                pids.add(pid)
        return sorted(pids)

    def _windows_status(self, component: str) -> dict[str, str]:
        ports = self._port_summary(component)
        open_ports = [str(item[2]) for item in ports if item[3]]
        active = "active" if open_ports else "inactive"
        pid = "-"
        if ports:
            pids = self._windows_listening_pids(ports[0][2])
            if pids:
                pid = ",".join(pids)
        return {"active": active, "enabled": "manual", "pid": pid}

    def component_status(self, component: str) -> dict[str, Any]:
        meta = self._component_meta(component)
        if self.platform == "linux":
            state = self._linux_status(component)
        else:
            state = self._windows_status(component)
        return {
            "component": component,
            "label": meta["label"],
            "description": meta["description"],
            "state": state,
            "ports": self._port_summary(component),
        }

    def print_status(self, target: str | None) -> None:
        print(f"平台: {self.platform}")
        print(f"部署方式: {self.platform_cfg['deployment_mode']}")
        for component in self._resolve_target(target):
            item = self.component_status(component)
            state = item["state"]
            print(f"- {item['label']} ({component})")
            print(f"  状态: {state['active']} | 自启: {state['enabled']} | PID: {state['pid']}")
            if item["ports"]:
                for name, host, port, is_open in item["ports"]:
                    print(f"  端口: {name} {host}:{port} -> {'open' if is_open else 'closed'}")

    def _linux_action(self, action: str, component: str) -> None:
        unit = self._component_meta(component).get("unit")
        if not unit:
            raise OpsError(f"Linux 组件 {component} 未配置 unit")
        self._run(self._linux_systemctl_base(component) + [action, unit], capture=True)

    def _windows_python_cmd(self) -> list[str]:
        candidate = self.root / "qq-bot" / "venv" / "Scripts" / "python.exe"
        if candidate.exists():
            return [str(candidate)]
        for cmd in (["py", "-3"], ["python"], ["python3"]):
            executable = cmd[0]
            if shutil.which(executable):
                return cmd
        return [sys.executable]

    def _windows_openclaw_cmd(self) -> list[str]:
        executable = shutil.which("openclaw.cmd") or shutil.which("openclaw")
        if executable:
            return [executable]
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        script = shutil.which("openclaw.ps1")
        if powershell and script:
            return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script]
        raise OpsError("Windows 未找到 openclaw 可执行入口，请确认 openclaw 已加入 PATH")

    def _windows_gateway_cmd(self) -> list[str]:
        base_cmd = self._windows_openclaw_cmd()
        command = list(base_cmd) + ["gateway"]
        openclaw_entry = Path(base_cmd[0])
        node_executable = shutil.which("node")
        if node_executable and openclaw_entry.name.lower() in {"openclaw.cmd", "openclaw.ps1"}:
            openclaw_main = openclaw_entry.parent / "node_modules" / "openclaw" / "openclaw.mjs"
            if openclaw_main.exists():
                command = [node_executable, str(openclaw_main), "gateway"]
        ports = self._component_meta("gateway").get("ports") or []
        if ports:
            command.extend(["--port", str(int(ports[0]["port"]))])
        return command

    def _windows_napcat_paths(self) -> tuple[str, str, str]:
        meta = self._component_meta("napcat")
        launcher = os.environ.get("BRAIN_SECRETARY_NAPCAT_LAUNCHER", meta.get("launcher", "D:\\NapCat\\NapCatWinBootMain.exe"))
        qq_exe = os.environ.get("BRAIN_SECRETARY_QQ_EXE", meta.get("qq_exe", "D:\\QQ\\QQ.exe"))
        hook_dll = os.environ.get("BRAIN_SECRETARY_NAPCAT_HOOK", meta.get("hook_dll", "D:\\NapCat\\NapCatWinBootHook.dll"))
        return launcher, qq_exe, hook_dll

    def _windows_start(self, component: str) -> None:
        if component == "gateway":
            self._spawn_detached(self._windows_gateway_cmd(), cwd=self.root)
            return
        if component == "bridge":
            python_cmd = self._windows_python_cmd()
            self._spawn_detached(python_cmd + ["main.py"], cwd=self.root / "qq-bot", log_file=self.root / "qq-bot" / "logs" / "ops-bridge.out.log")
            return
        if component == "napcat":
            launcher, qq_exe, hook_dll = self._windows_napcat_paths()
            self._spawn_detached([launcher, qq_exe, hook_dll], cwd=Path(launcher).resolve().parent)
            return
        raise OpsError(f"Windows 暂不支持单独启动组件: {component}")

    def _windows_stop(self, component: str) -> None:
        if component in {"gateway", "bridge"}:
            ports = self._port_summary(component)
            stopped = False
            for _, _, port, _ in ports:
                for pid in self._windows_listening_pids(port):
                    self._run(["taskkill", "/PID", pid, "/F"], check=False)
                    stopped = True
            if not stopped:
                print(f"- {component}: 未找到监听端口对应的进程")
            return
        if component == "napcat":
            for image in ("QQ.exe", "NapCatWinBootMain.exe"):
                self._run(["taskkill", "/IM", image, "/F"], check=False)
            for _, _, port, _ in self._port_summary(component):
                for pid in self._windows_listening_pids(port):
                    self._run(["taskkill", "/PID", pid, "/F"], check=False)
            return
        raise OpsError(f"Windows 暂不支持单独停止组件: {component}")

    def _perform_action(self, action: str, target: str | None) -> None:
        components = self._resolve_target(target)
        ordered = list(components)
        if action == "stop":
            ordered = list(reversed(ordered))
        print(f"平台: {self.platform} | 部署方式: {self.platform_cfg['deployment_mode']}")
        print(f"目标: {target or 'all'} -> {', '.join(ordered)}")
        for component in ordered:
            label = self._component_meta(component)["label"]
            print(f"- {action}: {label}")
            if self.platform == "linux":
                self._linux_action(action, component)
            elif self.platform == "windows":
                if action == "start":
                    self._windows_start(component)
                elif action == "stop":
                    self._windows_stop(component)
                elif action == "restart":
                    self._windows_stop(component)
                    self._windows_start(component)
                else:
                    raise OpsError(f"不支持的动作: {action}")
            else:
                raise OpsError(f"不支持的平台: {self.platform}")

    def print_info(self) -> None:
        project = self.manifest["project"]
        print(f"项目: {project['name']}")
        print(f"当前平台: {self.platform}")
        print(f"当前部署方式: {self.platform_cfg['deployment_mode']}")
        print(f"链路: {project['service_chain']}")
        print("\n关键模型:")
        for key, item in self.manifest["models"].items():
            print(f"- {key}: {item['runtime']}")
            for sub_key, sub_value in item.items():
                if sub_key == "runtime":
                    continue
                print(f"  {sub_key}: {sub_value}")
        print("\n关键路径:")
        for key, value in self.manifest["paths"].items():
            print(f"- {key}: {value}")
        extra_locations = self.platform_cfg.get("extra_locations", {})
        if extra_locations:
            print("\n平台附加路径:")
            for key, value in extra_locations.items():
                print(f"- {key}: {value}")
        print("\n当前平台分组:")
        for group_name, members in self.platform_cfg.get("groups", {}).items():
            print(f"- {group_name}: {', '.join(members)}")
        print("\n当前平台组件与端口:")
        for component in self.platform_cfg.get("groups", {}).get("all", []):
            meta = self._component_meta(component)
            print(f"- {meta['label']} ({component})")
            unit = meta.get("unit")
            if unit:
                print(f"  unit: {unit}")
            for port_name, host, port, _ in self._port_summary(component):
                print(f"  port: {port_name} {host}:{port}")
        print("\n平台部署:")
        for platform_name, platform_cfg in self.manifest["platforms"].items():
            print(f"- {platform_name}: {platform_cfg['deployment_mode']}")
            for example in platform_cfg.get("usage_examples", []):
                print(f"  {example}")
        print("\n文档入口:")
        for key, value in project["primary_docs"].items():
            print(f"- {key}: {value}")

    def print_ports(self, target: str | None) -> None:
        for component in self._resolve_target(target):
            meta = self._component_meta(component)
            print(f"- {meta['label']} ({component})")
            ports = self._port_summary(component)
            if not ports:
                print("  无端口配置")
                continue
            for name, host, port, is_open in ports:
                print(f"  {name}: {host}:{port} -> {'open' if is_open else 'closed'}")

    def show_logs(self, target: str | None, lines: int, follow: bool) -> None:
        components = self._resolve_target(target)
        if len(components) != 1:
            valid = ", ".join(sorted(self.platform_cfg["components"].keys()))
            raise OpsError(f"logs 只支持单个组件，请使用: {valid}")
        component = components[0]
        meta = self._component_meta(component)
        if self.platform == "linux":
            if meta.get("log_path"):
                log_path = Path(meta["log_path"])
                resolved = log_path if log_path.is_absolute() else (self.root / log_path)
                cmd = ["tail", "-n", str(lines), str(resolved)]
                if follow:
                    cmd = ["tail", "-f", "-n", str(lines), str(resolved)]
                self._run(cmd, capture=False)
                return
            unit = meta.get("unit")
            if not unit:
                raise OpsError(f"组件 {component} 未配置日志来源")
            cmd = self._linux_journalctl_base(component) + ["-u", unit, "-n", str(lines), "--no-pager"]
            if follow:
                cmd = self._linux_journalctl_base(component) + ["-u", unit, "-f", "-n", str(lines)]
            self._run(cmd, capture=False)
            return
        log_path = meta.get("log_path")
        if log_path:
            resolved = (self.root / log_path).resolve() if not Path(log_path).is_absolute() else Path(log_path)
            if follow:
                self._run(["powershell", "-NoProfile", "-Command", f"Get-Content -Path '{resolved}' -Wait -Tail {lines}"], capture=False)
            else:
                self._run(["powershell", "-NoProfile", "-Command", f"Get-Content -Path '{resolved}' -Tail {lines}"], capture=False)
            return
        raise OpsError(f"Windows 组件 {component} 暂未配置日志来源")
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Brain Secretary 运维脚本")
    parser.add_argument("command", choices=["info", "status", "start", "stop", "restart", "ports", "logs"], help="运维动作")
    parser.add_argument("target", nargs="?", default=None, help="all/backend/frontend/gateway/bridge/napcat/model_proxy/public_proxy")
    parser.add_argument("-n", "--lines", type=int, default=80, help="logs 输出行数")
    parser.add_argument("-f", "--follow", action="store_true", help="logs 持续跟随")
    parser.add_argument("--dry-run", action="store_true", help="只打印命令，不实际执行")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    manager = OpsManager(dry_run=args.dry_run)
    try:
        if args.command == "info":
            manager.print_info()
        elif args.command == "status":
            manager.print_status(args.target)
        elif args.command == "ports":
            manager.print_ports(args.target)
        elif args.command == "logs":
            manager.show_logs(args.target, lines=args.lines, follow=args.follow)
        elif args.command in {"start", "stop", "restart"}:
            manager._perform_action(args.command, args.target)
        else:
            raise OpsError(f"不支持的命令: {args.command}")
        return 0
    except OpsError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        print(f"命令执行失败: {stderr}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
