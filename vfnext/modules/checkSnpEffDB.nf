process checkSnpEffDB{
    publishDir "${params.outDir}", mode: "copy"
    label "singlethread"
    
    input:
        val(genome_code)

    output:
        path("snpEffDB_entry_found.log")

    script:
    """
    python $projectDir/bin/checkSnpEffDB.py \
      --genome-code "${genome_code}" \
      --virus "${params.virus}" \
      --catalog "${params.snpEffDBCatalog}" \
      --output "snpEffDB_entry_found.log" \
      --published-output "${params.outDir}/snpEffDB_entry_found.log"
    """
}
