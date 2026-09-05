import { useEffect, useRef, useState } from 'react';
import { User, Lock, ArrowRight } from 'lucide-react';
import logoUrl from '../../assets/logo.png';
import { motion } from 'framer-motion';

const vertexSmokeySource = `
  attribute vec4 a_position;
  void main() { gl_Position = a_position; }
`;

const fragmentSmokeySource = `
precision mediump float;
uniform vec2 iResolution;
uniform float iTime;
uniform vec2 iMouse;
uniform vec3 u_color;

void mainImage(out vec4 fragColor, in vec2 fragCoord){
    vec2 uv = fragCoord / iResolution;
    vec2 centeredUV = (2.0 * fragCoord - iResolution.xy) / min(iResolution.x, iResolution.y);
    float time = iTime * 0.5;
    vec2 mouse = iMouse / iResolution;
    vec2 rippleCenter = 2.0 * mouse - 1.0;
    vec2 distortion = centeredUV;
    for (float i = 1.0; i < 8.0; i++) {
        distortion.x += 0.5 / i * cos(i * 2.0 * distortion.y + time + rippleCenter.x * 3.1415);
        distortion.y += 0.5 / i * cos(i * 2.0 * distortion.x + time + rippleCenter.y * 3.1415);
    }
    float wave = abs(sin(distortion.x + distortion.y + time));
    float glow = smoothstep(0.9, 0.2, wave);
    fragColor = vec4(u_color * glow, 1.0);
}

void main() { mainImage(gl_FragColor, gl_FragCoord.xy); }
`;

function SmokeyBackground({ color = '#f0a030', className = '' }: { color?: string; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [hovering, setHovering] = useState(false);

  const hexToRgb = (hex: string): [number, number, number] => {
    const r = parseInt(hex.substring(1, 3), 16) / 255;
    const g = parseInt(hex.substring(3, 5), 16) / 255;
    const b = parseInt(hex.substring(5, 7), 16) / 255;
    return [r, g, b];
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const gl = canvas.getContext('webgl');
    if (!gl) return;

    const compileShader = (type: number, source: string) => {
      const shader = gl.createShader(type);
      if (!shader) return null;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) { gl.deleteShader(shader); return null; }
      return shader;
    };

    const vs = compileShader(gl.VERTEX_SHADER, vertexSmokeySource);
    const fs = compileShader(gl.FRAGMENT_SHADER, fragmentSmokeySource);
    if (!vs || !fs) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, -1,1, 1,-1, 1,1]), gl.STATIC_DRAW);
    const pos = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(pos);
    gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);

    const iRes = gl.getUniformLocation(program, 'iResolution');
    const iT = gl.getUniformLocation(program, 'iTime');
    const iM = gl.getUniformLocation(program, 'iMouse');
    const uC = gl.getUniformLocation(program, 'u_color');

    const start = Date.now();
    const [r, g, b] = hexToRgb(color);
    gl.uniform3f(uC, r, g, b);

    let animFrame: number;
    const render = () => {
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(iRes, canvas.width, canvas.height);
      gl.uniform1f(iT, (Date.now() - start) / 1000);
      gl.uniform2f(iM, hovering ? mousePos.x : canvas.width / 2, hovering ? canvas.height - mousePos.y : canvas.height / 2);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      animFrame = requestAnimationFrame(render);
    };
    render();

    return () => cancelAnimationFrame(animFrame);
  }, [hovering, mousePos, color]);

  return (
    <div className={`absolute inset-0 w-full h-full overflow-hidden ${className}`}>
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
        }}
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
      />
      <div className="absolute inset-0 backdrop-blur-sm" />
    </div>
  );
}

export default function LoginForm({
  mode, onToggleMode, onSubmit, error, loading, email, setEmail, password, setPassword,
  confirm, setConfirm, displayName, setDisplayName,
}: {
  mode: 'login' | 'signup';
  onToggleMode: () => void;
  onSubmit: (e: React.FormEvent) => void;
  error: string;
  loading: boolean;
  email: string; setEmail: (v: string) => void;
  password: string; setPassword: (v: string) => void;
  confirm: string; setConfirm: (v: string) => void;
  displayName: string; setDisplayName: (v: string) => void;
}) {
  return (
    <div className="relative w-full min-h-screen flex items-center justify-center px-6 overflow-hidden">
      <SmokeyBackground color="#f0a030" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] as const }}
        className="relative z-10 w-full max-w-sm p-8 space-y-6 bg-white/10 backdrop-blur-lg rounded-2xl border border-white/20 shadow-2xl"
      >
        {/* Logo */}
        <div className="text-center">
          <img src={logoUrl} alt="CLPZ" className="mx-auto mb-4 h-12 w-auto" />
          <h2 className="text-3xl font-bold text-white">Welcome {mode === 'login' ? 'Back' : 'to CLPZ'}</h2>
          <p className="mt-2 text-sm text-gray-300">{mode === 'login' ? 'Sign in to continue' : 'Create your account to get started'}</p>
        </div>

        {error && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            className="p-3 text-xs text-red-300 bg-red-500/20 border border-red-500/30 rounded-lg"
          >{error}</motion.div>
        )}

        <form onSubmit={onSubmit} className="space-y-6">
          {/* Email */}
          <div className="relative z-0">
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder=" "
              className="block py-2.5 px-0 w-full text-sm text-white bg-transparent border-0 border-b-2 border-gray-300 appearance-none focus:outline-none focus:ring-0 focus:border-amber-400 peer" />
            <label className="absolute text-sm text-gray-300 duration-300 transform -translate-y-6 scale-75 top-3 -z-10 origin-[0] peer-focus:left-0 peer-focus:text-amber-400 peer-placeholder-shown:scale-100 peer-placeholder-shown:translate-y-0 peer-focus:scale-75 peer-focus:-translate-y-6">
              <User className="inline-block mr-2 -mt-1" size={16} />Email Address
            </label>
          </div>

          {/* Password */}
          <div className="relative z-0">
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder=" " minLength={6}
              className="block py-2.5 px-0 w-full text-sm text-white bg-transparent border-0 border-b-2 border-gray-300 appearance-none focus:outline-none focus:ring-0 focus:border-amber-400 peer" />
            <label className="absolute text-sm text-gray-300 duration-300 transform -translate-y-6 scale-75 top-3 -z-10 origin-[0] peer-focus:left-0 peer-focus:text-amber-400 peer-placeholder-shown:scale-100 peer-placeholder-shown:translate-y-0 peer-focus:scale-75 peer-focus:-translate-y-6">
              <Lock className="inline-block mr-2 -mt-1" size={16} />Password
            </label>
          </div>

          {mode === 'signup' && (
            <>
              <div className="relative z-0">
                <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required placeholder=" " minLength={6}
                  className="block py-2.5 px-0 w-full text-sm text-white bg-transparent border-0 border-b-2 border-gray-300 appearance-none focus:outline-none focus:ring-0 focus:border-amber-400 peer" />
                <label className="absolute text-sm text-gray-300 duration-300 transform -translate-y-6 scale-75 top-3 -z-10 origin-[0] peer-focus:left-0 peer-focus:text-amber-400 peer-placeholder-shown:scale-100 peer-placeholder-shown:translate-y-0 peer-focus:scale-75 peer-focus:-translate-y-6">
                  <Lock className="inline-block mr-2 -mt-1" size={16} />Confirm Password
                </label>
              </div>
              <div className="relative z-0">
                <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder=" "
                  className="block py-2.5 px-0 w-full text-sm text-white bg-transparent border-0 border-b-2 border-gray-300 appearance-none focus:outline-none focus:ring-0 focus:border-amber-400 peer" />
                <label className="absolute text-sm text-gray-300 duration-300 transform -translate-y-6 scale-75 top-3 -z-10 origin-[0] peer-focus:left-0 peer-focus:text-amber-400 peer-placeholder-shown:scale-100 peer-placeholder-shown:translate-y-0 peer-focus:scale-75 peer-focus:-translate-y-6">
                  <User className="inline-block mr-2 -mt-1" size={16} />Display Name (optional)
                </label>
              </div>
            </>
          )}

          {mode === 'login' && (
            <div className="flex items-center justify-between">
              <a href="#" className="text-xs text-gray-300 hover:text-white transition">Forgot Password?</a>
            </div>
          )}

          <button type="submit" disabled={loading}
            className="group w-full flex items-center justify-center py-3 px-4 bg-amber-500 hover:bg-amber-400 rounded-lg text-black font-semibold focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-amber-500 transition-all duration-300 disabled:opacity-50"
          >
            {loading ? 'Loading…' : (mode === 'login' ? 'Sign In' : 'Create Account')}
            <ArrowRight className="ml-2 h-5 w-5 transform group-hover:translate-x-1 transition-transform" />
          </button>
        </form>

        <div className="relative flex py-2 items-center">
          <div className="flex-grow border-t border-gray-400/30" />
          <span className="flex-shrink mx-4 text-gray-400 text-xs">OR</span>
          <div className="flex-grow border-t border-gray-400/30" />
        </div>

        <button type="button" className="w-full flex items-center justify-center py-2.5 px-4 bg-white/90 hover:bg-white rounded-lg text-gray-700 font-semibold transition-all duration-300">
          <svg className="w-5 h-5 mr-2" viewBox="0 0 48 48">
            <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8c-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039L38.802 8.841C34.553 4.806 29.613 2.5 24 2.5C11.983 2.5 2.5 11.983 2.5 24s9.483 21.5 21.5 21.5S45.5 36.017 45.5 24c0-1.538-.135-3.022-.389-4.417z"/>
            <path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12.5 24 12.5c3.059 0 5.842 1.154 7.961 3.039l5.839-5.841C34.553 4.806 29.613 2.5 24 2.5C16.318 2.5 9.642 6.723 6.306 14.691z"/>
            <path fill="#4CAF50" d="M24 45.5c5.613 0 10.553-2.306 14.802-6.341l-5.839-5.841C30.842 35.846 27.059 38 24 38c-5.039 0-9.345-2.608-11.124-6.481l-6.571 4.819C9.642 41.277 16.318 45.5 24 45.5z"/>
            <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571l5.839 5.841C44.196 35.123 45.5 29.837 45.5 24c0-1.538-.135-3.022-.389-4.417z"/>
          </svg>
          Sign in with Google
        </button>

        <p className="text-center text-xs text-gray-400">
          {mode === 'login' ? "Don't have an account?" : "Already have an account?"}{' '}
          <button type="button" onClick={onToggleMode} className="font-semibold text-amber-400 hover:text-amber-300 transition underline">
            {mode === 'login' ? 'Sign Up' : 'Log In'}
          </button>
        </p>
      </motion.div>
    </div>
  );
}
