
  let handle_tag_click = function(d) {
	  console.log(d.id)
	  if (!d.title) {
		window.open(`http://localhost:5002/view_tag/${d.id}`, '_blank')
	  }
	  else {
		window.open(`http://localhost:5002/view_doc/${d.id}`, '_blank')
	  }
  }

var svg = d3.select("svg"),
    width = +svg.attr("width"),
    height = +svg.attr("height");


var simulation = d3.forceSimulation()
    .force("link", d3.forceLink().id(function(d) { return d.id; }).distance(100))
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter(width / 2, height / 2));

d3.json("force.json", function(error, graph) {
  if (error) throw error;


// var color = d3.scaleOrdinal(d3.schemeGreys)
var color = d3.scaleOrdinal(d3.schemeBlues)

  var link = svg.append("g")
      .attr("class", "links")
    .selectAll("line")
    .data(graph.links)
    .enter().append("line")
      .attr("stroke-width", function(d) { return 1 })
	.attr("stroke", "#999")
		  .attr("stroke-opacity", 0.6)

  var node = svg.append("g")
      .attr("class", "nodes")
    .selectAll("g")
    .data(graph.nodes)
    .enter().append("g").attr("class", "node").on("click", d => handle_tag_click(d));
  
  var circles = node.append("circle")
      .attr("r", 10)
	  .style("fill", d => {
		if ("title" in d)
		  {
			  return "#FF2442"
		  }
		else { return "white" }

	  })
      .call(d3.drag()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended));

  var lables = node.append("text")
      .text(function(d) {
		if ('title' in d)
		  {
			return d.title;
		  }
		else {
        	return d.id;
		}
      })
	  .attr('fill', '#B980F0')
	  .style("z-index", 99)
      .attr('x', 6)
      .attr('y', 3);

  node.append("title")
      .text(function(d) { return d.i; });

  simulation
      .nodes(graph.nodes)
      .on("tick", ticked);

  simulation.force("link")
      .links(graph.links);

  function ticked() {
    link
        .attr("x1", function(d) { return d.source.x; })
        .attr("y1", function(d) { return d.source.y; })
        .attr("x2", function(d) { return d.target.x; })
        .attr("y2", function(d) { return d.target.y; });

    node
        .attr("transform", function(d) {
          return "translate(" + d.x + "," + d.y + ")";
        })
  }
});

function dragstarted(d) {
  if (!d3.event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x;
  d.fy = d.y;
}

function dragged(d) {
  d.fx = d3.event.x;
  d.fy = d3.event.y;
}

function dragended(d) {
  if (!d3.event.active) simulation.alphaTarget(0);
  d.fx = null;
  d.fy = null;
}


