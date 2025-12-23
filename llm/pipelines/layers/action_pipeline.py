# layers/action_pipeline.py
"""
Layer 3C: Action Pipeline (Script Generation + Strict Validation)

Purpose:
- Handle action requests (script generation, automation)
- Strict metadata validation (OS, role, security_level REQUIRED)
- CoT reasoning for quality scripts
- Ask user for missing critical parameters

Based on:
- REVISED_ROUTE_ARCHITECTURE.md - Layer 3C specification
- Strict parameter enforcement
"""

from __future__ import annotations
from typing import Callable, Optional, List
from dataclasses import dataclass
from datetime import datetime

from llm.core.context import RequestContext
from llm.prompts.cot_prompts import CoTSecurityAnalyzer
from llm.utils.parameter_inference import ParameterInferenceEngine
from llm.core.config import CONFIG
from .zt_enrichment import ZeroTrustEnricher, ZTEnrichment
from .output_validator import OutputValidator, ValidationResult

# Type alias
LLMCallable = Callable[[str], str]


@dataclass
class ActionQueryResult:
    """Action pipeline result"""
    success: bool
    answer: Optional[str] = None
    script: Optional[str] = None
    missing_params: List[str] = None  # If parameters missing
    user_prompt_message: Optional[str] = None  # Message to ask user
    model_used: str = "unknown"
    response_time_s: float = 0.0
    estimated_cost: float = 0.0
    zt_enrichment: Optional[ZTEnrichment] = None  # Zero Trust enrichment
    validation: Optional[ValidationResult] = None  # Output validation result


class ActionPipeline:
    """
    Layer 3C: Action Pipeline Handler

    Design:
    - Strict metadata validation
    - ALWAYS require: os, role, security_level for scripts
    - If missing → Ask user before proceeding
    - Use CoT reasoning for quality scripts
    - RAG-based security guidelines

    Integration:
    - Called after Layer 2 identifies "action_request" intent
    - Returns script OR request for missing parameters
    """

    def __init__(
        self,
        llm_large: LLMCallable,
        llm_small: Optional[LLMCallable] = None,
        rag_builder: Optional[Callable] = None,
        debug: bool = False,
    ):
        """
        Args:
            llm_large: Large model callable (scripts need quality)
            llm_small: Small model for ZT enrichment (optional)
            rag_builder: RAG context builder (for security guidelines)
            debug: Enable debug logging
        """
        self.llm_large = llm_large
        self.llm_small = llm_small or llm_large
        self.rag_builder = rag_builder
        self.debug = debug

        # CoT analyzer for script generation
        self.cot_analyzer = CoTSecurityAnalyzer(use_few_shot=True)

        # Parameter inference engine
        self.param_engine = ParameterInferenceEngine(debug=debug)

        # Zero Trust enrichment
        self.zt_enricher = ZeroTrustEnricher(llm=self.llm_small, debug=debug)

        # Output validator
        self.validator = OutputValidator(llm=self.llm_small, use_llm_validation=True, debug=debug)

        self.stats = {
            "total_requests": 0,
            "successful_scripts": 0,
            "missing_params_count": 0,
            "total_cost": 0.0,
        }

    def handle(self, ctx: RequestContext) -> ActionQueryResult:
        """
        Handle action request (script generation)

        Args:
            ctx: Request context

        Returns:
            ActionQueryResult (script OR missing params message)

        Logic:
        1. Validate metadata (os, role, security_level)
        2. If missing critical params → Ask user
        3. If all params present → Generate script with CoT
        4. Return structured result
        """
        start_time = datetime.now()

        self.stats["total_requests"] += 1

        if self.debug:
            print(f"[ActionPipeline] Processing action request")

        # STEP 1: Validate metadata
        missing_params = self._validate_metadata(ctx)

        if missing_params:
            if self.debug:
                print(f"[ActionPipeline] Missing parameters: {missing_params}")

            self.stats["missing_params_count"] += 1

            # Build user prompt message
            user_message = self._build_missing_params_message(missing_params, ctx.user_question)

            response_time = (datetime.now() - start_time).total_seconds()

            return ActionQueryResult(
                success=False,
                missing_params=missing_params,
                user_prompt_message=user_message,
                response_time_s=response_time,
                estimated_cost=0.0,  # No LLM call yet
            )

        # STEP 2: All params present → Generate script

        if self.debug:
            print(f"[ActionPipeline] All params present, generating script...")
            print(f"  OS: {ctx.os}")
            print(f"  Role: {ctx.role}")
            print(f"  Security Level: {ctx.security_level}")

        # STEP 2A: Zero Trust Enrichment
        zt_enrichment = self.zt_enricher.enrich(ctx)

        if self.debug:
            print(f"[ActionPipeline] ZT Enrichment complete:")
            print(f"  Principles: {', '.join(zt_enrichment.zt_principles[:3])}...")
            print(f"  Standards: {', '.join(zt_enrichment.standards[:3])}...")
            print(f"  Impact: {zt_enrichment.impact_level}")

        # Store in context for prompt building
        ctx.zt_principles = zt_enrichment.zt_principles
        ctx.standards = zt_enrichment.standards
        ctx.extra["impact_level"] = zt_enrichment.impact_level
        ctx.extra["rollback_approach"] = zt_enrichment.rollback_approach

        # STEP 2B: RAG retrieval (security guidelines for script)
        if self.rag_builder:
            try:
                rag_context = self.rag_builder.retrieve_context(ctx.user_question)
                if rag_context:
                    ctx.retrieved_context = rag_context

                    if self.debug:
                        print(f"[ActionPipeline] RAG context retrieved")
            except Exception as e:
                if self.debug:
                    print(f"[ActionPipeline] RAG failed: {e}")

        # STEP 2C: CoT script generation
        script = self._generate_script_with_cot(ctx)

        # STEP 2D: Output Validation
        validation = self.validator.validate(
            output=script,
            intent="action_request",
            use_deep_check=True  # Critical for scripts
        )

        if not validation.is_valid:
            if self.debug:
                print(f"[ActionPipeline] Validation found {len(validation.issues)} issue(s)")

            # Use corrected output if available, otherwise use original with warning
            if validation.corrected_output:
                script = validation.corrected_output
                if self.debug:
                    print(f"[ActionPipeline] Using corrected output")
            else:
                # Add validation warnings to script
                warning = f"\n\n# VALIDATION WARNINGS:\n"
                for issue in validation.issues[:3]:  # Max 3 warnings
                    warning += f"# - {issue}\n"
                warning += "# Please review carefully before using.\n"
                script = script + warning

        # Success stats
        self.stats["successful_scripts"] += 1
        estimated_cost = 0.0025 + 0.0005 + 0.001  # Script + ZT + Validation
        self.stats["total_cost"] += estimated_cost

        response_time = (datetime.now() - start_time).total_seconds()

        return ActionQueryResult(
            success=True,
            answer=script,
            script=script,
            model_used="large+CoT+ZT+Validation",
            response_time_s=response_time,
            estimated_cost=estimated_cost,
            zt_enrichment=zt_enrichment,
            validation=validation,
        )

    def _validate_metadata(self, ctx: RequestContext) -> List[str]:
        """
        Validate critical metadata for script generation

        Required parameters:
        - os: Target operating system
        - role: User role (affects script complexity/explanations)
        - security_level: Security strictness level

        Args:
            ctx: Request context

        Returns:
            List of missing parameter names (empty if all present)
        """
        missing = []

        # Check OS
        if not ctx.os or ctx.os == "unknown":
            missing.append("os")

        # Check role
        if not ctx.role or ctx.role == "unknown":
            missing.append("role")

        # Check security_level
        if not ctx.security_level or ctx.security_level == "unknown":
            missing.append("security_level")

        return missing

    def _build_missing_params_message(self, missing_params: List[str], question: str) -> str:
        """
        Build user-friendly message to request missing parameters

        Args:
            missing_params: List of missing parameter names
            question: Original user question

        Returns:
            User prompt message
        """
        # Try to infer from question first
        inferred_params = self.param_engine.infer_all(question)

        message_parts = [
            "⚠️ **Eksik Bilgiler**",
            "",
            "Script oluşturmak için aşağıdaki bilgilere ihtiyacım var:",
            ""
        ]

        # Build param requests with suggestions
        if "os" in missing_params:
            suggested_os = inferred_params.get("os", "ubuntu_22_04")
            message_parts.extend([
                f"1. **İşletim Sistemi** (örn: ubuntu_22_04, centos_9, windows_server_2022)",
                f"   → Tespit edilen: `{suggested_os}` (doğru mu?)",
                ""
            ])

        if "role" in missing_params:
            suggested_role = inferred_params.get("role", "sysadmin")
            message_parts.extend([
                f"2. **Rol** (örn: sysadmin, developer, devops, security)",
                f"   → Tespit edilen: `{suggested_role}` (doğru mu?)",
                ""
            ])

        if "security_level" in missing_params:
            suggested_level = inferred_params.get("security_level", "balanced")
            message_parts.extend([
                f"3. **Güvenlik Seviyesi** (minimal, balanced, strict)",
                f"   → Tespit edilen: `{suggested_level}` (doğru mu?)",
                ""
            ])

        message_parts.extend([
            "**Örnek Kullanım:**",
            "```",
            f"OS: {inferred_params.get('os', 'ubuntu_22_04')}",
            f"Rol: {inferred_params.get('role', 'sysadmin')}",
            f"Güvenlik Seviyesi: {inferred_params.get('security_level', 'balanced')}",
            "```",
            "",
            "Lütfen bu bilgileri doğrulayın veya düzeltin, ardından tekrar deneyin."
        ])

        return "\n".join(message_parts)

    def _generate_script_with_cot(self, ctx: RequestContext) -> str:
        """
        Generate script using CoT reasoning

        Args:
            ctx: Request context (with all required params)

        Returns:
            Generated script
        """
        if self.debug:
            print("[ActionPipeline] Generating script with CoT reasoning")

        # Build enhanced prompt for script generation
        cot_prompt = self._build_script_prompt(ctx)

        # LLM call
        raw_response = self.llm_large(cot_prompt)

        # Parse CoT response
        ctx = self.cot_analyzer.parse_cot_response(raw_response, ctx)

        return ctx.final_answer if ctx.final_answer else raw_response

    def _build_script_prompt(self, ctx: RequestContext) -> str:
        """
        Build specialized prompt for script generation

        Args:
            ctx: Request context

        Returns:
            Prompt string
        """
        rag_context = ctx.retrieved_context if ctx.retrieved_context else "No specific CIS guidelines available."

        prompt = f"""You are an expert security engineer. Generate a production-ready hardening script.

**User Request:**
{ctx.user_question}

**Target Environment:**
- OS: {ctx.os}
- User Role: {ctx.role}
- Security Level: {ctx.security_level}
- ZT Maturity: {ctx.zt_maturity if hasattr(ctx, 'zt_maturity') else 'medium'}

**Security Guidelines (CIS Benchmark):**
{rag_context}

**Requirements:**
1. Production-ready bash/PowerShell script
2. Include error handling and rollback
3. Add comments explaining each step
4. Follow security best practices
5. Match security_level strictness:
   - minimal: Basic hardening only
   - balanced: Recommended settings
   - strict: Maximum security (may impact usability)

**Output Format:**
```bash
#!/bin/bash
# Hardening script for {ctx.os}
# Security Level: {ctx.security_level}
# Generated for: {ctx.role}

# [Your script here]
```

**Script:**"""

        return prompt

    def get_stats(self) -> dict:
        """Get usage statistics"""
        total = self.stats["total_requests"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "success_rate": self.stats["successful_scripts"] / total,
            "missing_params_rate": self.stats["missing_params_count"] / total,
            "avg_cost_per_script": self.stats["total_cost"] / max(self.stats["successful_scripts"], 1),
        }


# Convenience function
def handle_action_request(
    question: str,
    llm_large: LLMCallable,
    rag_builder: Optional[Callable] = None,
    context: Optional[RequestContext] = None,
    debug: bool = False,
) -> ActionQueryResult:
    """
    Quick action request handler

    Usage:
        result = handle_action_request(
            "Ubuntu 22.04 için SSH hardening scripti yaz",
            llm_large=openai_llm,
            rag_builder=rag_builder
        )

        if not result.success:
            print(result.user_prompt_message)  # Ask user for missing params
        else:
            print(result.script)  # Show generated script
    """
    from llm.core.context import RequestContext

    if context is None:
        context = RequestContext(user_question=question)

    pipeline = ActionPipeline(
        llm_large=llm_large,
        rag_builder=rag_builder,
        debug=debug,
    )

    return pipeline.handle(context)


# ─────────────────────────────────────────────
# Test & Examples
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Mock LLM
    def mock_llm_large(prompt: str) -> str:
        return """```bash
#!/bin/bash
# SSH Hardening Script for Ubuntu 22.04
# Security Level: strict

echo "Starting SSH hardening..."

# Disable root login
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# Change default port
sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config

# Restart SSH
systemctl restart sshd

echo "SSH hardening complete!"
```"""

    # Mock RAG builder
    class MockRAGBuilder:
        def retrieve_context(self, question: str) -> str:
            return "CIS Benchmark:\n- Disable root login\n- Change default port\n- Use key-based auth"

    print("="*70)
    print("ACTION PIPELINE - TEST")
    print("="*70)

    pipeline = ActionPipeline(
        llm_large=mock_llm_large,
        rag_builder=MockRAGBuilder(),
        debug=True,
    )

    # Test Case 1: Missing parameters
    print("\n" + "="*70)
    print("TEST 1: Missing Parameters")
    print("="*70)

    from llm.core.context import RequestContext

    ctx_incomplete = RequestContext(
        user_question="SSH hardening scripti yaz",
        # Missing: os, role, security_level
    )

    result1 = pipeline.handle(ctx_incomplete)

    if not result1.success:
        print("\n✅ CORRECTLY DETECTED MISSING PARAMS")
        print(f"Missing: {result1.missing_params}")
        print(f"\n{result1.user_prompt_message}")
    else:
        print("\n❌ ERROR: Should have detected missing params!")

    # Test Case 2: All parameters present
    print("\n" + "="*70)
    print("TEST 2: All Parameters Present")
    print("="*70)

    ctx_complete = RequestContext(
        user_question="SSH hardening scripti yaz",
        os="ubuntu_22_04",
        role="sysadmin",
        security_level="strict",
    )

    result2 = pipeline.handle(ctx_complete)

    if result2.success:
        print("\n✅ SCRIPT GENERATED")
        print(f"Model: {result2.model_used}")
        print(f"Cost: ${result2.estimated_cost:.4f}")
        print(f"Time: {result2.response_time_s:.2f}s")
        print(f"\nScript preview:\n{result2.script[:200]}...")
    else:
        print("\n❌ ERROR: Should have generated script!")
        print(f"Message: {result2.user_prompt_message}")

    print("\n" + "="*70)
    print("STATISTICS")
    print("="*70)
    stats = pipeline.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)
