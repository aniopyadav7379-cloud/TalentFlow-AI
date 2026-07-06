"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorAlert } from "@/components/ui/feedback";
import { Input, Label } from "@/components/ui/input";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";

// Mirrors the backend's UserRegister schema exactly (min_length=8 on password).
const schema = z.object({
  full_name: z.string().min(2, "Enter your full name"),
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setServerError(null);
    try {
     await registerUser({
  ...values,
  role: "recruiter",
});
      router.push("/jobs");
    } catch (err) {
      setServerError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    }
  }

  return (
    <Card>
      <h1 className="mb-1 text-lg font-semibold text-foreground">Create your account</h1>
      <p className="mb-6 text-sm text-muted-foreground">Start ranking candidates in minutes.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {serverError && <ErrorAlert message={serverError} />}

        <div>
          <Label htmlFor="full_name">Full name</Label>
          <Input id="full_name" placeholder="Asha Kumar" error={errors.full_name?.message} {...register("full_name")} />
        </div>

        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" placeholder="you@company.com" error={errors.email?.message} {...register("email")} />
        </div>

        <div>
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            placeholder="At least 8 characters"
            error={errors.password?.message}
            {...register("password")}
          />
        </div>

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          Create account
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:text-primary-hover">
          Sign in
        </Link>
      </p>
    </Card>
  );
}
