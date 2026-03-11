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
    rag_sources: List = None  # RAG source metadata (PDF + YAML chunks)

    def __post_init__(self):
        if self.rag_sources is None:
            self.rag_sources = []
        if self.missing_params is None:
            self.missing_params = []


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

        # STEP 2B: RAG retrieval (security guidelines + YAML scripts for script generation)
        rag_sources = []
        if self.rag_builder:
            try:
                rag_context, raw_results = self.rag_builder.retrieve_balanced(ctx.user_question)
                if rag_context and raw_results:
                    ctx.retrieved_context = rag_context
                    # Store raw results so _build_script_prompt can use YAML scripts directly
                    ctx.extra["rag_raw_results"] = raw_results

                    for result in raw_results:
                        metadata = result.get("metadata", {})
                        section_id = metadata.get("section_id") or metadata.get("rule_id") or ""
                        section_title = metadata.get("section_title") or metadata.get("title") or ""
                        if section_id and section_title:
                            section = f"{section_id} - {section_title}"
                        elif section_id:
                            section = section_id
                        elif section_title:
                            section = section_title
                        else:
                            section = "N/A"
                        rag_sources.append({
                            "score": result.get("score", 0.0),
                            "source": metadata.get("benchmark_product") or metadata.get("source_id") or "CIS Benchmark",
                            "section": section,
                            "doc_type": metadata.get("doc_type", ""),
                            "text": result.get("text", "")[:500],
                        })

                    if self.debug:
                        yaml_count = sum(1 for r in raw_results if r.get("metadata", {}).get("doc_type") == "yaml_rule")
                        print(f"[ActionPipeline] RAG OK — {len(raw_results)} chunks ({yaml_count} YAML rules)")
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
            rag_sources=rag_sources,
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
        Build specialized prompt for script generation.
        YAML rule chunks (with actual bash scripts) are surfaced in a dedicated
        section so the LLM uses them as direct references instead of generating
        scripts from scratch.

        Args:
            ctx: Request context

        Returns:
            Prompt string
        """
        raw_results: list = ctx.extra.get("rag_raw_results", [])

        # Separate YAML rule chunks from PDF benchmark chunks
        yaml_chunks = [r for r in raw_results if r.get("metadata", {}).get("doc_type") == "yaml_rule"]
        pdf_chunks  = [r for r in raw_results if r.get("metadata", {}).get("doc_type") != "yaml_rule"]

        # --- YAML scripts section ---
        yaml_section = ""
        if yaml_chunks:
            parts = []
            for r in yaml_chunks:
                meta = r.get("metadata", {})
                rule_id = meta.get("rule_id", "?")
                title   = meta.get("title", "")
                score   = r.get("score", 0.0)
                text    = r.get("text", "")
                parts.append(
                    f"### Rule {rule_id} — {title} (relevance: {score:.2f})\n{text}"
                )
            yaml_section = (
                "\n**CIS Rule Scripts (from hardening database — use these as reference scripts):**\n"
                + "\n---\n".join(parts)
                + "\n"
            )

        # --- PDF benchmark context section ---
        if pdf_chunks:
            pdf_context_parts = []
            for idx, r in enumerate(pdf_chunks, 1):
                meta = r.get("metadata", {})
                source = meta.get("benchmark_product") or meta.get("source_id") or "CIS Benchmark"
                section_id    = meta.get("section_id") or meta.get("section") or ""
                section_title = meta.get("section_title") or meta.get("rule_id") or ""
                section = f"{section_id} - {section_title}" if section_id and section_title else section_id or section_title or "N/A"
                pdf_context_parts.append(
                    f"[{idx}] {source} | {section}\n{r.get('text', '').strip()}"
                )
            pdf_section = "\n**CIS Benchmark Guidance:**\n" + "\n\n".join(pdf_context_parts) + "\n"
        elif ctx.retrieved_context:
            pdf_section = f"\n**CIS Benchmark Guidance:**\n{ctx.retrieved_context}\n"
        else:
            pdf_section = "\n**CIS Benchmark Guidance:** No specific guidelines retrieved.\n"

        os_target = ctx.os or "linux"
        script_type = "PowerShell" if "windows" in os_target.lower() else "Bash"
        shebang     = "" if "windows" in os_target.lower() else "#!/usr/bin/env bash\n"

        prompt = f"""You are an expert security engineer. Generate a production-ready {script_type} hardening script.

**User Request:**
{ctx.user_question}

**Target Environment:**
- OS: {os_target}
- User Role: {ctx.role}
- Security Level: {ctx.security_level}
- ZT Maturity: {getattr(ctx, 'zt_maturity', 'medium')}
{yaml_section}{pdf_section}
**Script Requirements:**
1. Production-ready {script_type} script with proper error handling
2. Each step must have a comment explaining what it does and why (CIS reference)
3. Include a rollback/undo note for each change
4. Adjust strictness to security_level:
   - minimal: Only critical controls, avoid breaking changes
   - balanced: Recommended CIS Level 1 controls
   - strict: CIS Level 1 + Level 2, maximum hardening
5. If CIS Rule Scripts are provided above, adapt them directly — do NOT ignore them
6. Output ONLY the script inside a code block, no extra prose

**Generated Script:**
```{script_type.lower()}
{shebang}# Hardening script — {os_target}
# Security Level: {ctx.security_level} | Role: {ctx.role}
# Generated by AI-Powered OS Hardening System
"""

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
