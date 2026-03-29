import { useEffect, useState } from "react";
import { loginUser, registerUser } from "./api";
import { getUiText } from "./i18n";

const EMPTY_MEMBER = { name: "", birth_date: "" };

function AuthForm({ onLoginSuccess, activeTab: controlledActiveTab, language = "uz" }) {
  const [activeTab, setActiveTab] = useState("login");
  const [authError, setAuthError] = useState("");
  const [authSuccess, setAuthSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [loginForm, setLoginForm] = useState({
    username: "demo",
    password: "demo123",
  });

  const [registerForm, setRegisterForm] = useState({
    full_name: "",
    passport_number: "",
    birth_date: "",
    address: "",
    username: "",
    password: "",
    family_members: [EMPTY_MEMBER],
  });

  const ui = getUiText(language);

  const resetForm = () => {
    setLoginForm({ username: "demo", password: "demo123" });
    setRegisterForm({
      full_name: "",
      passport_number: "",
      birth_date: "",
      address: "",
      username: "",
      password: "",
      family_members: [EMPTY_MEMBER],
    });
    setAuthError("");
    setAuthSuccess("");
  };

  useEffect(() => {
    if (controlledActiveTab === "login" || controlledActiveTab === "register") {
      setActiveTab(controlledActiveTab);
    }
  }, [controlledActiveTab]);

  useEffect(() => {
    setAuthError("");
    setAuthSuccess("");
  }, [activeTab]);

  const handleLogin = async (event) => {
    event.preventDefault();
    setAuthError("");
    setAuthSuccess("");
    setIsSubmitting(true);

    try {
      const response = await loginUser({
        username: loginForm.username.trim(),
        password: loginForm.password,
      });

      setAuthError("");
      setAuthSuccess(ui.authLoginSuccess);
      resetForm();
      onLoginSuccess?.({
        token: response.access_token,
        username: loginForm.username.trim().toLowerCase(),
      });
    } catch {
      setAuthSuccess("");
      setAuthError(ui.backendFriendlyError);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegister = async (event) => {
    event.preventDefault();
    setAuthError("");
    setAuthSuccess("");
    setIsSubmitting(true);

    const payload = {
      full_name: registerForm.full_name.trim(),
      passport_number: registerForm.passport_number.trim(),
      birth_date: registerForm.birth_date,
      address: registerForm.address.trim(),
      username: registerForm.username.trim(),
      password: registerForm.password,
      family_members: registerForm.family_members
        .map((member) => ({
          name: member.name.trim(),
          birth_date: member.birth_date,
        }))
        .filter((member) => member.name && member.birth_date),
    };

    try {
      await registerUser(payload);

      const loginResponse = await loginUser({
        username: payload.username,
        password: payload.password,
      });

      setAuthError("");
      setAuthSuccess(ui.authRegisterSuccess);
      resetForm();
      onLoginSuccess?.({
        token: loginResponse.access_token,
        username: payload.username.toLowerCase(),
      });
    } catch (error) {
      setAuthSuccess("");
      if (error.message?.includes("Login") || error.message?.includes("Authenticate")) {
        setAuthError(ui.backendFriendlyError);
        window.setTimeout(() => {
          setActiveTab("login");
        }, 2000);
      } else {
        setAuthError(ui.backendFriendlyError);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const updateFamilyMember = (index, field, value) => {
    setRegisterForm((prev) => {
      const nextMembers = [...prev.family_members];
      nextMembers[index] = { ...nextMembers[index], [field]: value };
      return { ...prev, family_members: nextMembers };
    });
  };

  const addFamilyMember = () => {
    setRegisterForm((prev) => ({
      ...prev,
      family_members: [...prev.family_members, { ...EMPTY_MEMBER }],
    }));
  };

  const removeFamilyMember = (index) => {
    setRegisterForm((prev) => ({
      ...prev,
      family_members: prev.family_members.filter((_, currentIndex) => currentIndex !== index),
    }));
  };

  return (
    <section className="gov-card rounded-3xl p-5 sm:p-6">
      <div className="mb-4 flex rounded-2xl bg-slate-100 p-1">
        <button
          type="button"
          onClick={() => setActiveTab("login")}
          className={`w-1/2 rounded-xl px-3 py-2 text-sm font-semibold transition ${
            activeTab === "login" ? "bg-slate-900 text-white shadow" : "text-slate-700 hover:bg-white"
          }`}
        >
          {ui.login}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("register")}
          className={`w-1/2 rounded-xl px-3 py-2 text-sm font-semibold transition ${
            activeTab === "register" ? "bg-slate-900 text-white shadow" : "text-slate-700 hover:bg-white"
          }`}
        >
          {ui.register}
        </button>
      </div>

      {activeTab === "login" ? (
        <form onSubmit={handleLogin} className="space-y-3">
          <input
            value={loginForm.username}
            onChange={(event) => setLoginForm((prev) => ({ ...prev, username: event.target.value }))}
            placeholder={ui.username}
            className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-[0_8px_18px_rgba(15,23,42,0.08)] outline-none focus:border-cyan-400"
          />
          <input
            value={loginForm.password}
            type="password"
            onChange={(event) => setLoginForm((prev) => ({ ...prev, password: event.target.value }))}
            placeholder={ui.password}
            className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-[0_8px_18px_rgba(15,23,42,0.08)] outline-none focus:border-cyan-400"
          />
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-2xl bg-gradient-to-r from-slate-900 via-blue-900 to-cyan-700 px-4 py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-60"
          >
            {isSubmitting ? ui.signingIn : ui.login}
          </button>
        </form>
      ) : (
        <form onSubmit={handleRegister} className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <input
            value={registerForm.full_name}
            onChange={(event) => setRegisterForm((prev) => ({ ...prev, full_name: event.target.value }))}
            placeholder={ui.fullName}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-[0_8px_18px_rgba(15,23,42,0.08)] outline-none focus:border-cyan-400 sm:col-span-2"
          />
          <input
            value={registerForm.passport_number}
            onChange={(event) => setRegisterForm((prev) => ({ ...prev, passport_number: event.target.value }))}
            placeholder={ui.passportNumber}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-[0_8px_18px_rgba(15,23,42,0.08)] outline-none focus:border-cyan-400"
          />
          <input
            value={registerForm.birth_date}
            type="date"
            onChange={(event) => setRegisterForm((prev) => ({ ...prev, birth_date: event.target.value }))}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-[0_8px_18px_rgba(15,23,42,0.08)] outline-none focus:border-cyan-400"
          />
          <input
            value={registerForm.address}
            onChange={(event) => setRegisterForm((prev) => ({ ...prev, address: event.target.value }))}
            placeholder={ui.address}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-[0_8px_18px_rgba(15,23,42,0.08)] outline-none focus:border-cyan-400 sm:col-span-2"
          />
          <input
            value={registerForm.username}
            onChange={(event) => setRegisterForm((prev) => ({ ...prev, username: event.target.value }))}
            placeholder={ui.username}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-[0_8px_18px_rgba(15,23,42,0.08)] outline-none focus:border-cyan-400"
          />
          <input
            value={registerForm.password}
            type="password"
            onChange={(event) => setRegisterForm((prev) => ({ ...prev, password: event.target.value }))}
            placeholder={ui.password}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-[0_8px_18px_rgba(15,23,42,0.08)] outline-none focus:border-cyan-400"
          />

          <div className="rounded-2xl border border-cyan-200/40 bg-cyan-50/70 p-3 sm:col-span-2">
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-sm font-bold text-cyan-900">{ui.familyMembers} ({ui.optional})</h4>
              <button
                type="button"
                onClick={addFamilyMember}
                className="rounded-xl bg-white px-3 py-1.5 text-xs font-semibold text-cyan-800 transition hover:bg-cyan-100"
              >
                {ui.add}
              </button>
            </div>

            <div className="space-y-2">
              {registerForm.family_members.map((member, index) => (
                <div key={`${index}-${member.name}`} className="grid grid-cols-1 gap-2 sm:grid-cols-12">
                  <input
                    value={member.name}
                    onChange={(event) => updateFamilyMember(index, "name", event.target.value)}
                    placeholder={ui.memberName}
                    className="rounded-xl border border-cyan-100 bg-white px-3 py-2 text-sm outline-none focus:border-cyan-400 sm:col-span-6"
                  />
                  <input
                    value={member.birth_date}
                    type="date"
                    onChange={(event) => updateFamilyMember(index, "birth_date", event.target.value)}
                    className="rounded-xl border border-cyan-100 bg-white px-3 py-2 text-sm outline-none focus:border-cyan-400 sm:col-span-4"
                  />
                  <button
                    type="button"
                    onClick={() => removeFamilyMember(index)}
                    disabled={registerForm.family_members.length === 1}
                    className="rounded-xl bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50 sm:col-span-2"
                  >
                    {ui.remove}
                  </button>
                </div>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="sm:col-span-2 rounded-2xl bg-gradient-to-r from-slate-900 via-blue-900 to-cyan-700 px-4 py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-60"
          >
            {isSubmitting ? ui.creatingAccount : ui.register}
          </button>
        </form>
      )}

      {authSuccess ? (
        <p className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{authSuccess}</p>
      ) : authError ? (
        <p className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{authError}</p>
      ) : null}
    </section>
  );
}

export default AuthForm;
