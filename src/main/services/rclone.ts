import { spawn, ChildProcess } from 'child_process';

export interface RcloneProgress {
  transferred: number;
  total: number;
  percentage: number;
  speed: string;
  eta: string;
}

export interface RcloneOptions {
  remote: string;
  remotePath: string;
  localPath: string;
  rclonePath?: string;
}

let activeProcess: ChildProcess | null = null;

export function uploadFile(
  localFile: string,
  options: RcloneOptions,
  onProgress: (progress: RcloneProgress) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const rcloneBin = options.rclonePath || 'rclone';
    const destination = `${options.remote}:${options.remotePath}`;

    const args = [
      'copy',
      localFile,
      destination,
      '--progress',
      '--stats-one-line',
      '--stats', '1s',
    ];

    activeProcess = spawn(rcloneBin, args);
    let stderr = '';

    activeProcess.stderr?.on('data', (data: Buffer) => {
      const text = data.toString();
      stderr += text;

      // Parse rclone progress output
      const transferredMatch = text.match(/Transferred:\s+([\d.]+\s+\w+)\s+\/\s+([\d.]+\s+\w+)/);
      const percentMatch = text.match(/(\d+)%/);
      const speedMatch = text.match(/,\s+([\d.]+\s+\w+\/s)/);
      const etaMatch = text.match(/ETA\s+(\S+)/);

      if (percentMatch) {
        onProgress({
          transferred: 0,
          total: 100,
          percentage: parseInt(percentMatch[1], 10),
          speed: speedMatch ? speedMatch[1] : '',
          eta: etaMatch ? etaMatch[1] : '',
        });
      }

      void transferredMatch;
    });

    activeProcess.on('close', (code) => {
      activeProcess = null;
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`rclone exited with code ${code}: ${stderr}`));
      }
    });

    activeProcess.on('error', (err) => {
      activeProcess = null;
      reject(err);
    });
  });
}

export function pauseUpload(): void {
  if (activeProcess) {
    activeProcess.kill('SIGSTOP');
  }
}

export function resumeUpload(): void {
  if (activeProcess) {
    activeProcess.kill('SIGCONT');
  }
}

export function cancelUpload(): void {
  if (activeProcess) {
    activeProcess.kill('SIGTERM');
    activeProcess = null;
  }
}

export function checkRcloneAvailable(rclonePath?: string): Promise<boolean> {
  return new Promise((resolve) => {
    const bin = rclonePath || 'rclone';
    const proc = spawn(bin, ['version']);
    proc.on('close', (code) => resolve(code === 0));
    proc.on('error', () => resolve(false));
  });
}
