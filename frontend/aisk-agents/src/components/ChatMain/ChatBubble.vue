<template>
    <!-- Check if event is 'user_message' -->
    <li
      v-if="props.event === 'user_message'" 
      class=" flex  px-4 items-start    gap-x-2 sm:gap-x-4"
    >
    
      <div class="grow text-end space-y-3 ">
        <!-- Card -->
        <div class="inline-block flex justify-end ">
          <p class="text-[16px]  text-left color-primary-brandGray max-w-[80%] w-auto">
            {{ props.data }}
            
          </p>
        </div>
        <!-- End Card -->
      </div>
      <UserAvatar :type="user" />
    </li>
    
    <!-- For all other cases -->
    <li v-else class="  relative  px-4 items-start gap-x-2 sm:gap-x-4">
      
      <div class="w-full relative flex items-center  ">
    
    
        
        <UserAvatar :type="fetchProvider()||'Agent'" />   
        <div class="grow relative text-start space-y-3">
        <!-- Card -->
        <div class="inline-block" >
       <div class="relative p-4 flex items-center capitalize space-y-3 font-inter font-semibold 
       text-[16px] leading-[18px] tracking-[0px] text-center capitalize"> {{ fetchProvider()||'' }} Agent
       <!-- Menu button: visible on hover -->
      
      
       <button

           v-if="parsedData.agent_type==='sales_leads'||parsedData.agent_type==='financial_analysis'
           ||parsedData.agent_type==='deep_research'"
        type="button"
        class="  group-hover:opacity-100 transition-opacity duration-200"
        @click.stop="toggleMenu"
        @mousedown.stop
        aria-label="Open menu"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="5" r="1" />
          <circle cx="12" cy="12" r="1" />
          <circle cx="12" cy="19" r="1" />
        </svg>
      </button>
    
      <!-- Popover menu -->
      <div
        v-if="activeMenu"
        class="absolute right-1 top-8 bg-white border border-gray-200 shadow-lg rounded z-30"
        @click.stop
      >
       
        <!-- <button
          class="flex items-center w-full px-4 py-2 hover:bg-gray-100 text-left"
          
        >
          <svg class="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7" />
            <polyline points="12 3 12 12" />
            <polyline points="9 6 12 3 15 6" />
          </svg>
          View Report
        </button> -->
        <button
          class="flex items-center w-full px-4 py-2 hover:bg-gray-100 text-left"
          @click="generatePDFFromHtml"
        >
          <svg class="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Download PDF
        </button>
      </div></div>
</div>

</div>
        </div>
        <div class="w-full bg-white  ">          
          <AnalysisTimeline 
      :isLoading="isLoading" 
      :parsedData="parsedData" 
      :workflowData="workflowData" 
      :presentMetadata="parsedData.metadata" 
      :plannerText="plannerText" 
    />
        <component :id="'chat-'+messageId" :is="selectedComponent" :parsed="parsedData" />
    </div>
    
    </li>
  </template>
  
  <script setup>
  import { computed, defineProps, ref,watch,nextTick } from 'vue'
  
  import UserAvatar from '@/components/Common/UIComponents/UserAvtar.vue'
  import AssistantComponent from '@/components/ChatMain/ResponseTypes/AssistantComponent.vue'
  import UserProxyComponent from '@/components/ChatMain/ResponseTypes/UserProxyComponent.vue'
  import SalesLeadComponent from '@/components/ChatMain/ResponseTypes/SalesLeadsComponent.vue'
  import EducationalComponent from '@/components/ChatMain/EducationalComponent.vue'
  import UnknownTypeComponent from '@/components/ChatMain/ResponseTypes/UnknownTypeComponent.vue'
  import FinancialAnalysisComponent from '@/components/ChatMain/ResponseTypes/FinancialAnalysisComponent.vue'
  import DeepResearchComponent from '@/components/ChatMain/ResponseTypes//DeepResearchComponent.vue'
  import ErrorComponent from '@/components/ChatMain/ResponseTypes/ErrorComponent.vue'
  import AnalysisTimeline from '@/components/ChatMain/AnalysisTimeline.vue'

  import html2canvas from "html2canvas";
  import jsPDF from "jspdf";
  import html2pdf from 'html2pdf.js'


  
  function fetchProvider() {
  // Check if workflowData is an array and has elements
  if (!props.workflowData || !Array.isArray(props.workflowData)) {
    return null;
  }
  for (let i = 0; i < props.workflowData.length; i++) {
    if (props.workflowData[i].hasOwnProperty('llm_provider')) {
      return props.workflowData[i].llm_provider;
    }
  }
  // Return null if no object with 'llm_provider' is found
  return null;
}

  const formattedDuration=(duration) =>{
      // Format duration to 2 decimal places
      return duration?.toFixed(2);
    }
  
  // Define props
  const props = defineProps({
    data: {
      type: String,
      required: true
    },
    event: {
      type: String,
      required: true
    },
    plannerText: {
      type: String,
      required: true
    },
    metadata: {
      type: Object,
      required: true
    },
    provider: {
      type: String,
      required: true
    },
    messageId: {
      type: String,
      required: true
    },
    
  workflowData: {
    type: [],
    required: false // Ensure it's always provided
  },
  
  })
  const presentMetadata = computed(() => {


if (!parsedData.metadata) return null;

return parsedData.metadata;
});

  const presentMetadataOld = computed(() => {


  if (!props.metadata) return null;

  return props.metadata;
});







  
  // Parse the JSON string safely
  const parsedData = computed(() => {
    try {
      return JSON.parse(props.data)
    } catch (error) {
      console.error('Error parsing data in ChatBubble:', error)
      return {}
    }
  })
  
  // Choose which sub-component to display based on agent_type
  const selectedComponent = computed(() => {
    switch (parsedData.value.agent_type) {
      case 'assistant':
        return AssistantComponent
      case 'educational_content':
        return EducationalComponent
      case 'user_proxy':
        return UserProxyComponent
      case 'sales_leads':
        return SalesLeadComponent
      case 'financial_analysis':
        return FinancialAnalysisComponent
      case 'deep_research':
        return DeepResearchComponent
      case 'error':
        return ErrorComponent
      default:
        return UnknownTypeComponent
    }
  })
  
  // Define isOpen; if not passed as prop, define it as a ref
  const isOpen = ref(false)  // adjust as needed; for instance, based on statusText or other logic
  const collapsed = ref(true)
function toggleCollapse() {
  collapsed.value = !collapsed.value
}

const activeMenu = ref(false);




function toggleMenu() {
    activeMenu.value = !activeMenu.value;
  }


  const headerConfig = ref({
  // Replace with your actual SVG markup string or generate one dynamically
  SVGMarkup: `
    <svg
      class="logo shrink-0 p-1 rounded-sm"
      width="37"
      height="38"
      viewBox="0 0 37 38"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient
          id="brandGradient"
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="0"
          x2="1000"
          y2="0"
        >
          <!-- Animate x2 to create a moving effect -->
          <animate
            attributeName="x2"
            from="1000"
            to="0"
            dur="5s"
            repeatCount="indefinite"
          />
          <stop offset="0%" stop-color="#EE7624" />
          <stop offset="100%" stop-color="#EE7624" />
        </linearGradient>
      </defs>
      <path
        d="M36.0662 37.4535H34.0626V12.6172C34.0653 10.0763 33.0744 7.63742 31.3063 5.83311C29.5381 4.02879 27.1363 3.00558 24.6253 2.98684H11.441C8.96466 2.98684 6.58972 3.98224 4.83867 5.75407C3.08761 7.5259 2.10388 9.929 2.10388 12.4347C2.10388 14.9405 3.08761 17.3436 4.83867 19.1155C6.58972 20.8873 8.96466 21.8827 11.441 21.8827H12.6933C13.2616 21.8008 13.8407 21.8433 14.3912 22.0075C14.9419 22.1716 15.4512 22.4536 15.8848 22.8342C16.3184 23.2149 16.6661 23.6853 16.9044 24.2137C17.1427 24.7421 17.266 25.3162 17.266 25.897C17.266 26.4778 17.1427 27.0519 16.9044 27.5803C16.6661 28.1087 16.3184 28.5792 15.8848 28.9598C15.4512 29.3405 14.9419 29.6224 14.3912 29.7866C13.8407 29.9507 13.2616 29.9933 12.6933 29.9114H1.52588e-05V27.8839H12.7234C12.9897 27.9033 13.2571 27.8669 13.5089 27.7771C13.7606 27.6874 13.9915 27.546 14.1869 27.362C14.3824 27.1779 14.5383 26.9551 14.6449 26.7074C14.7514 26.4598 14.8064 26.1925 14.8064 25.9224C14.8064 25.6522 14.7514 25.3849 14.6449 25.1373C14.5383 24.8896 14.3824 24.6668 14.1869 24.4827C13.9915 24.2987 13.7606 24.1573 13.5089 24.0676C13.2571 23.9777 12.9897 23.9414 12.7234 23.9608H11.4711C8.44285 23.9716 5.53412 22.7661 3.38345 20.6089C1.23277 18.4517 0.0159207 15.5192 1.52588e-05 12.4551C0.0159198 9.39534 1.23035 6.46691 3.37697 4.31192C5.52359 2.15694 8.4272 0.951297 11.4511 0.959391H24.6453C27.6819 0.991395 30.5836 2.2331 32.7215 4.41533C34.8594 6.59757 36.0611 9.54446 36.0662 12.6172V37.4535Z"
        fill="url(#brandGradient)"
      />
      <path
        d="M32.2893 37.4537H30.2856V12.6174C30.2886 11.096 29.7014 9.63408 28.6505 8.546C27.5995 7.45791 26.1686 6.83051 24.6653 6.79865H11.441C9.95838 6.79865 8.53648 7.39461 7.4881 8.45542C6.43972 9.51624 5.85075 10.955 5.85075 12.4553C5.85075 13.9554 6.43972 15.3942 7.4881 16.455C8.53648 17.5158 9.95838 18.1118 11.441 18.1118H11.5512L12.7735 18.2436C14.7928 18.2517 16.7263 19.0711 18.1486 20.5217C19.5708 21.9722 20.3654 23.935 20.3574 25.9783C20.3494 28.0216 19.5396 29.978 18.106 31.4172C16.6725 32.8564 14.7327 33.6603 12.7134 33.6522H0V31.6247H12.7234C14.206 31.6247 15.628 31.0288 16.6763 29.968C17.7246 28.9072 18.3136 27.4684 18.3136 25.9681C18.3136 24.468 17.7246 23.0292 16.6763 21.9684C15.628 20.9076 14.206 20.3116 12.7234 20.3116H12.6132L11.401 20.1798C10.401 20.1798 9.41097 19.9805 8.4872 19.5933C7.56343 19.2062 6.72407 18.6386 6.01704 17.9233C5.31002 17.2079 4.74918 16.3585 4.36653 15.4238C3.9839 14.4891 3.78696 13.4873 3.78696 12.4755C3.78696 11.4638 3.9839 10.4619 4.36653 9.52719C4.74918 8.59247 5.31002 7.74315 6.01704 7.02774C6.72407 6.31233 7.56343 5.74484 8.4872 5.35766C9.41097 4.97048 10.401 4.7712 11.401 4.7712H24.6453C26.6845 4.80577 28.6286 5.6498 30.0586 7.12132C31.4885 8.59285 32.2896 10.574 32.2893 12.6377V37.4537Z"
        fill="url(#brandGradient)"
      />
      <path
        d="M12.7234 37.4535H0V35.426H12.7234C15.1998 35.426 17.5747 34.4306 19.3257 32.6588C21.0767 30.887 22.0605 28.4839 22.0605 25.9781C22.0605 23.4723 21.0767 21.0693 19.3257 19.2975C17.5747 17.5256 15.1998 16.5302 12.7234 16.5302H11.4711C10.9028 16.6121 10.3237 16.5696 9.77312 16.4054C9.22251 16.2412 8.71317 15.9593 8.27959 15.5787C7.84601 15.1981 7.49831 14.7276 7.26001 14.1992C7.02172 13.6707 6.8984 13.0966 6.8984 12.5158C6.8984 11.935 7.02172 11.3609 7.26001 10.8325C7.49831 10.3042 7.84601 9.83368 8.27959 9.45304C8.71317 9.0724 9.22251 8.79046 9.77312 8.62629C10.3237 8.46212 10.9028 8.41956 11.4711 8.5015H24.6453C25.7198 8.53061 26.7406 8.98378 27.4894 9.76418C28.2381 10.5446 28.6556 11.5903 28.6527 12.6781V37.4535H26.649V12.6172C26.6551 12.0793 26.4569 11.5595 26.0952 11.1652C25.7336 10.771 25.2359 10.5323 24.7054 10.4986H11.441C11.1747 10.4791 10.9073 10.5155 10.6555 10.6053C10.4037 10.6951 10.1729 10.8365 9.97744 11.0205C9.78207 11.2045 9.62616 11.4273 9.51958 11.675C9.413 11.9227 9.358 12.19 9.358 12.4601C9.358 12.7303 9.413 12.9975 9.51958 13.2452C9.62616 13.4929 9.78207 13.7157 9.97744 13.8997C10.1729 14.0838 10.4037 14.2252 10.6555 14.3149C10.9073 14.4047 11.1747 14.441 11.441 14.4217H12.6933C15.7117 14.4176 18.6081 15.627 20.7452 17.7838C22.8824 19.9407 24.0853 22.8681 24.0892 25.9223C24.0932 28.9766 22.898 31.9072 20.7665 34.0698C18.635 36.2322 15.7418 37.4494 12.7234 37.4535Z"
        fill="url(#brandGradient)"
      />
    </svg>
  `,
  topHeading: parsedData.agent_type==='sales_leads'?"Sales Lead":parsedData.agent_type==='financial_analysis'?"Financial Report":"Research  Report",
  subHeading: 'Generated with SambaNova Agents'
})

async function generatePDFFromHtmOLd() {
  // Close the menu if open
  toggleMenu();

  // Get the content element to convert
  const contentElement = document.getElementById('chat-' + props.messageId);
  if (!contentElement) {
    console.error('Content element not found');
    return;
  }

  // Create a temporary wrapper element
  const wrapper = document.createElement('div');
  // Apply padding to match your PDF margins
  wrapper.style.padding = '10mm';

  // Create a header container for dynamic SVG logo and text
  const headerContainer = document.createElement('div');
  headerContainer.style.textAlign = 'center';
  headerContainer.style.marginBottom = '10mm';

  // Insert dynamic header content using template literals
  headerContainer.innerHTML = `
    <div style="display: flex; flex-direction: column; align-items: center;">
      ${headerConfig.value.SVGMarkup}
      <h1 style="margin: 5mm 0 0 0; font-size: 18pt;">${headerConfig.value.topHeading}</h1>
      <p style="margin: 0; font-size: 12pt;">${headerConfig.value.subHeading}</p>
    </div>
  `;

  // Append header and cloned content to the wrapper
  wrapper.appendChild(headerContainer);
  const clonedContent = contentElement.cloneNode(true);
  // Remove any extra top margin to avoid overlap
  clonedContent.style.marginTop = '0mm';
  wrapper.appendChild(clonedContent);

  // Define html2pdf options; margin is set to 0 because we're handling it in the wrapper
  const pdfOpts = {
    margin: 0,
    filename: 'financial_analysis.pdf',
    pagebreak: { mode: ['css', 'legacy'] },
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true, letterRendering: true },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
  };

  try {
    await html2pdf().set(pdfOpts).from(wrapper).save();
  } catch (e) {
    console.error('PDF error:', e);
  }
}


async function generatePDFFromHtml() {
  toggleMenu()
  const element = document.getElementById('chat-'+props.messageId)
  
 // Create a temporary wrapper element
 const wrapper = document.createElement('div');
  // Apply padding to match your PDF margins
  wrapper.style.padding = '10mm';

  // Create a header container for dynamic SVG logo and text
  const headerContainer = document.createElement('div');
  headerContainer.style.textAlign = 'center';
  headerContainer.style.marginBottom = '10mm';

  // Insert dynamic header content using template literals
  headerContainer.innerHTML = `
    <div style="display: flex; flex-direction: column; align-items: center;">
      ${headerConfig.value.SVGMarkup}
      <h1 style="margin: 5mm 0 0 0; font-size: 18pt;">${headerConfig.value.topHeading}</h1>
      <p style="margin: 0; font-size: 12pt;">${headerConfig.value.subHeading}</p>
    </div>
  `;


  // Append header and cloned content to the wrapper
  // wrapper.appendChild(headerContainer);
  // element.prepend(wrapper);
  // Remove any extra top margin to avoid overlap
  // clonedContent.style.marginTop = '0mm';
  // wrapper.appendChild(clonedContent);


  const pdfOpts = {
    margin: [10, 10],
    filename: 'download.pdf',
    pagebreak: { mode: ['css', 'legacy'] },
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: {
      scale: 2,
      useCORS: true,
      letterRendering: true
    },
    jsPDF: {
      unit: 'mm',
      format: 'a4',
      orientation: 'portrait'
    }
  }

  try {
    
    await html2pdf().set(pdfOpts).from(element).save()
  } catch(e) {
    console.error('PDF error:', e)
  }
  
}

async function generateSelectablePDF() {
  // For testing, we use the static element with id "pdf-content".
  const contentEl = document.getElementById('chat-'+props.messageId)
  if (!contentEl) {
    console.error('Content element not found')
    return
  }

  // Create a wrapper element to house the content with explicit styling.
  const wrapper = document.createElement('div')
  // Set a fixed width (in pixels) that approximates your intended PDF layout.
  // You may adjust this value (e.g., 800px) to better match your design.
  wrapper.style.width = '800px'
  wrapper.style.padding = '20px'
  wrapper.style.background = '#fff'
  // Inject the inner HTML from our test content.
  wrapper.innerHTML = contentEl.innerHTML
  
  // Append the wrapper offscreen so that html2canvas can fully render it.
  wrapper.style.position = 'absolute'
  wrapper.style.top = '-10000px'
  document.body.appendChild(wrapper)

  // Wait for the DOM to update and a short delay to ensure full rendering.
  await nextTick()
  setTimeout(() => {
    // Create a new jsPDF instance.
    // Using unit: 'px' here helps to more directly map from CSS pixels.
    const doc = new jsPDF({
      unit: 'px',
      format: 'a4',
      orientation: 'portrait'
    })

    // Render the wrapper using jsPDF's html() method.
    doc.html(wrapper, {
      callback: function (doc) {
        console.log('PDF rendering complete. Saving PDF...')
        doc.save('output.pdf')
        // Clean up the temporary wrapper.
        document.body.removeChild(wrapper)
      },
      // Set starting coordinates inside the PDF.
      x: 10,
      y: 10,
      // Specify the content width in the PDF (in px).
      width: 800,
      // Adjust html2canvas options.
      html2canvas: {
        scale: 1, // lower scale if text is too large; you can try 1 or 1.5
        useCORS: true,
        // This helps html2canvas know the intended width of the element.
        windowWidth: wrapper.scrollWidth
      }
    })
  }, 500) // A delay of 500ms; adjust if necessary
}

  </script>
  <style>

</style>