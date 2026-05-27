<script setup lang="ts">

</script>

<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold mb-4">Explanation</h1>
    <p class="mb-4">
      Our AI tool helps you identify connections between key events (Key Events) in scientific literature when developing Adverse Outcome Pathways (AOPs). The system analyzes scientific publications in PDF format that you provide. This allows researchers to gain faster insights into complex biological processes and supports the development of AOPs.
    </p>
    
    <h2 class="text-xl font-semibold mb-2">How Does the AI System Work?</h2>
    <h3 class="text-lg font-semibold mb-2">Data Submission</h3>
    <p class="mb-4">
      You upload relevant scientific publications and define the Key Events you want to analyze.
    </p>
    <h3 class="text-lg font-semibold mb-2">Analysis and Pattern Recognition</h3>
    <p class="mb-4">
      The system uses advanced algorithms to identify patterns and relationships between these Key Events within the provided literature.
    </p>
    <h3 class="text-lg font-semibold mb-2">Generating Suggestions</h3>
    <p class="mb-4">
      Based on the detected connections, the AI system presents possible insights that experts can further investigate.
    </p>
    <h3 class="text-lg font-semibold mb-2">Expanding the Analysis</h3>
    <p class="mb-4">
      You can search for additional Key Events to refine the results or discover new relationships.
    </p>
    <h3 class="text-lg font-semibold mb-2">Control Over Relevance</h3>
    <p class="mb-4">
      With an adjustable slider, you determine the relevance level of the extracted text fragments, ensuring the analysis aligns with your needs.
    </p>
    <h3 class="text-lg font-semibold mb-2">Visualization of Connections</h3>
    <p class="mb-4">
      The AI tool provides a visual representation of the relationships between Key Events, allowing you to interpret insights quickly and clearly.
    </p>
    
    <h2 class="text-xl font-semibold mb-2">Important Disclaimers</h2>
    <h3 class="text-lg font-semibold mb-2">Limitations of AI and Interpretation</h3>
    <div class="important-box mb-4">
      <ul class="list-disc list-inside">
        <li><strong class="highlight">The AI tool can hallucinate:</strong> This means that the tool may sometimes suggest incorrect or misleading connections. Although the model does not introduce new terms, it may establish relationships that are not scientifically validated. Human validation is therefore essential.</li>
        <li><strong class="highlight">Not a replacement for human expertise:</strong> The system’s results must always be reviewed and validated by scientists. AI supports research but does not replace it.</li>
        <li><strong class="highlight">Bias and limitations:</strong> The AI tool depends on the provided scientific literature. Any biases in the data may influence the AI’s suggestions.</li>
      </ul>
    </div>
    <h3 class="text-lg font-semibold mb-2">How Does the System Make Decisions?</h3>
    <p class="mb-4">
      Our AI model utilizes Natural Language Processing (NLP) and machine learning to analyze text from articles. It identifies statistical patterns, semantic relationships, and context but does not understand the content as a human would.
    </p>
    
    <h2 class="text-xl font-semibold mb-2">Privacy and Data Protection (GDPR)</h2>
    <div class="important-box mb-4">
      <p>
        <span class="highlight">The provided scientific publications and data may be analyzed via external databases, which can pose privacy risks depending on the document content.</span> Researchers must ensure that they do not share confidential or personal data without permission and in compliance with applicable GDPR regulations. <span class="highlight">Our system operates on a cloud-based model—please take this into account when handling sensitive documents.</span>
      </p>
    </div>
    
    <h2 class="text-xl font-semibold mb-2">Use of Cloud Models</h2>
    <div class="important-box mb-4">
      <p>
        <span class="highlight">We understand that cloud-based AI models are privacy sensitive.</span> However, to ensure the accuracy of identifying relationships, we intentionally use cloud models such as OpenAI or Deepseek. For researchers seeking an AI solution within a more secure environment, an internal version of ChatGPT could be a potential option.
      </p>
    </div>
    
    <h2 class="text-xl font-semibold mb-2">Conclusion</h2>
    <p class="mb-4">
      Our AI tool is a powerful resource for discovering relationships between Key Events in scientific literature. It accelerates research and supports AOP development, but it is crucial to critically assess the results and continue leveraging human expertise. Do you have any questions or suggestions about the system? Feel free to contact us at <a href="mailto:masterhcaistudent@hu.nl">masterhcaistudent@hu.nl</a>
    </p>
  </div>
</template>

<style scoped>
.highlight {
  color: #5046e4;
}
.important-box {
  border: 2px solid #5046e4;
  padding: 1rem;
  border-radius: 0.5rem;
  background-color: #f9f9ff;
}
</style>

