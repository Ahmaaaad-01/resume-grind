import { GoogleLogin } from '@react-oauth/google';
import { useAuth } from '../context/AuthContext';
import { useState } from 'react';

export function LoginPage() {
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center">
      <div className="bg-bg-surface border border-border-subtle rounded-2xl p-8 max-w-sm w-full text-center">
        <h1 className="text-2xl font-bold text-text-heading mb-2">PM Job Pipeline</h1>
        <p className="text-sm text-text-body mb-8">
          Discover PM jobs, score them, and generate tailored resumes.
        </p>

        <div className="flex justify-center mb-4">
          <GoogleLogin
            onSuccess={async (response) => {
              if (response.credential) {
                try {
                  await login(response.credential);
                } catch (err) {
                  setError(`Login failed: ${err}`);
                }
              }
            }}
            onError={() => setError('Google sign-in failed')}
            theme="filled_black"
            size="large"
            width={280}
          />
        </div>

        {error && (
          <p className="text-xs text-status-red mt-4">{error}</p>
        )}

        <p className="text-xs text-text-body/50 mt-6">
          Sign in with Google to get started.
        </p>
      </div>
    </div>
  );
}
