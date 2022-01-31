function zoomed() {
	root.attr("transform", d3.event.transform);
}


let handle_tag_click = function(d) {
  console.log(d.id)
  if (!d.title) {
	window.open(`/concept/${d.id}`, '_blank')
  }
  else {
	window.open(`/doc/${d.id}`, '_blank')
  }
}

var svg = d3.select("svg"),
    width = +svg.attr("width"),
    height = +svg.attr("height");

let root = svg.select("#root");

let tickIndex = 0;
var simulation = d3.forceSimulation()
    .force("link", d3.forceLink().id(function(d) { return d.id; }).distance(100))
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter(width / 2, height / 2))

d3.json("/static/force.json", function(error, graph) {
  if (error) throw error;


// var color = d3.scaleOrdinal(d3.schemeGreys)
var color = d3.scaleOrdinal(d3.schemeBlues)

  var link = root.append("g")
      .attr("class", "links")
    .selectAll("line")
    .data(graph.links)
    .enter().append("line")
      .attr("stroke-width", function(d) { return 1 })
	.attr("stroke", "#999")
		  .attr("stroke-opacity", 0.6)

  var node = root.append("g")
      .attr("class", "nodes")
    .selectAll("g")
    .data(graph.nodes)
    .enter().append("g").attr("id", d => d.id).attr("class", "node").on("click", d => handle_tag_click(d));
	
  
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
	zoomFit(1);
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

let circles = root.selectAll("circle");
const zoom = d3.zoom().on("zoom", zoomed);
svg.call(zoom);


function zoomFit(initial) {
	// modification of http://bl.ocks.org/TWiStErRob/b1c62730e01fe33baa2dea0d0aa29359
	let scale;
	initial = initial || false;
	if (initial)
	{
		tickIndex++;
		if (tickIndex != 5) return; // wait for some of the graph to load
		svg.style("visibility", "visible"); // then make it visible and fit size
		scale = 1.15;
	}
	else scale = 3;
	let nodes = root.selectAll(".node").data()
    var bounds = root.node().getBBox();
    var parent = root.node().parentElement;
    var fullWidth = parent.clientWidth || parent.parentNode.clientWidth,
        fullHeight = parent.clientHeight || parent.parentNode.clientHeight;
    var width = bounds.width,
        height = bounds.height;
    var midX = bounds.x + width / 2,
        midY = bounds.y + height / 2;
    if (width == 0 || height == 0) return; // nothing to fit
    scale = scale / Math.max(width / fullWidth, height / fullHeight);
    var translate = [fullWidth / 2 - scale * midX, fullHeight / 2 - scale * midY];

	svg
	  .transition()
	  .duration(0) // milliseconds
	  .call(zoom.transform, d3.zoomIdentity
	  	.translate(translate[0], translate[1])
	  	.scale(scale)
	  );
}
let finderForm = document.getElementById("finder_form");
finderForm.onsubmit = function(e) {
	e.preventDefault();
	let id = document.getElementById("finder_input").value;
	let node = root.select("#" + id);
	node.select("text").style("display", "inline");
    var bbox = node.node().getBBox(),
       bounds = [[bbox.x, bbox.y],[bbox.x + bbox.width, bbox.y + bbox.height]];

	let transform = node.attr("transform").replace("translate(", "").replace(")", "").split(",");
    var dx = bounds[1][0] - bounds[0][0],
      dy = bounds[1][1] - bounds[0][1],
      x = (bounds[0][0] + bounds[1][0]) / 2 + parseFloat(transform[0]),
      y = (bounds[0][1] + bounds[1][1]) / 2 + parseFloat(transform[1]),
      scale = Math.max(1, Math.min(8, 0.3 / Math.max(dx / width, dy / height))),
      translate = [width / 2 - scale * x + 500, height / 2 - scale * y + 150];

	console.log(translate)
	  svg.transition()
		  .duration(750)
		  .call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale))
}
