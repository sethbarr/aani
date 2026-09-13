# Required secondary analyses. All warnings and session details are captured.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) stop("Usage: Rscript mixed_effects.R input.csv output_dir")
input <- args[[1]]
output <- args[[2]]
dir.create(output, recursive = TRUE, showWarnings = FALSE)
options(warn = 1)
if (!requireNamespace("lme4", quietly = TRUE)) stop("lme4 is required; model not estimable")
data <- read.csv(input, stringsAsFactors = FALSE)
required <- c("active", "rejected", "species_match_fraction", "phytochemistry_records", "family", "genus", "compound_id")
if (!all(required %in% names(data))) stop("Missing mixed-model columns")
if (length(unique(data$active)) < 2L || length(unique(data$rejected)) < 2L) stop("Constant outcome or exposure")
for (column in c("family", "genus", "compound_id")) {
  data[[column]] <- factor(data[[column]])
  if (nlevels(data[[column]]) < 2L || nlevels(data[[column]]) >= nrow(data)) {
    stop(paste("Insufficient replication for required random effect:", column))
  }
}
results <- data.frame()
diagnostics <- data.frame()
for (adjusted in c(FALSE, TRUE)) {
  terms <- "rejected"
  dropped <- character()
  if (length(unique(data$species_match_fraction)) > 1L) {
    terms <- c(terms, "species_match_fraction")
  } else {
    dropped <- c(dropped, "species_match_fraction (constant)")
  }
  if (adjusted && length(unique(data$phytochemistry_records)) > 1L) {
    terms <- c(terms, "log1p(phytochemistry_records)")
  } else if (adjusted) {
    dropped <- c(dropped, "log1p(phytochemistry_records) (constant)")
  }
  formula <- as.formula(paste("active ~", paste(terms, collapse = " + "),
                              "+ (1 | family) + (1 | genus) + (1 | compound_id)"))
  fit <- try(lme4::glmer(formula, data = data, family = binomial(),
                         control = lme4::glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 200000))), silent = TRUE)
  model_name <- if (adjusted) "effort_adjusted" else "unadjusted"
  if (inherits(fit, "try-error")) {
    diagnostics <- rbind(diagnostics, data.frame(model = model_name, status = "not_estimable",
                          singular = NA, message = as.character(fit), dropped = paste(dropped, collapse = "; ")))
    next
  }
  coefficient <- summary(fit)$coefficients["rejected", ]
  convergence <- fit@optinfo$conv$lme4$messages
  singular <- lme4::isSingular(fit)
  status <- if (length(convergence) || singular) "diagnostic_warning" else "ok"
  if (any(fitted(fit) < 1e-8 | fitted(fit) > 1 - 1e-8)) {
    convergence <- c(convergence, "Extreme fitted probabilities: inspect separation")
    status <- "diagnostic_warning"
  }
  diagnostics <- rbind(diagnostics, data.frame(model = model_name, status = status,
                        singular = singular, message = paste(convergence, collapse = "; "),
                        dropped = paste(dropped, collapse = "; ")))
  results <- rbind(results, data.frame(model = model_name, log_odds = coefficient[[1]],
                   standard_error = coefficient[[2]], odds_ratio = exp(coefficient[[1]]),
                   lower_95 = exp(coefficient[[1]] - 1.96 * coefficient[[2]]),
                   upper_95 = exp(coefficient[[1]] + 1.96 * coefficient[[2]]),
                   n_rows = nrow(data), n_genera = nlevels(data$genus), n_families = nlevels(data$family)))
}
write.csv(results, file.path(output, "coefficients.csv"), row.names = FALSE)
write.csv(diagnostics, file.path(output, "diagnostics.csv"), row.names = FALSE)
capture.output(sessionInfo(), file = file.path(output, "session_info.txt"))
